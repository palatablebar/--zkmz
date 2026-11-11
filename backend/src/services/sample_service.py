"""Sample job lifecycle: create → run (PIT engine) → 校验报告.

运行链路口径：
1. 建 job 时冻结 ``params_snapshot``（标签集、特征版本、边界、范围），用于审计；
2. 运行时重新读取「当前特征定义」计算——所以 owner 修正边界策略后重跑立即生效；
3. ``pit_engine`` 真算每个 ``(entity, label_time)`` × 每个特征的聚合并检测泄漏；
4. 结果落 ``sample_row``（逐样本特征 JSON + 泄漏标记）与 ``sample_job.result_json``。
"""
from datetime import timedelta
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.constants.enums import BoundaryPolicy, FailureReason, JobStatus
from src.constants.error_codes import AppError, ErrorCode
from src.models import EntityEvent, FeatureDef, LabelRow, LabelSet, SampleJob, SampleRow
from src.services import feature_service
from src.services.pit_engine import (
    Event,
    LabelRow as EngineLabelRow,
    PitFailure,
    build_report,
    normalize_events,
    parse_range,
)
from src.utils.logger import log_event
from src.utils.serialize import job_out
from src.utils.timefmt import iso_ms_z, iso_z, utcnow

MAX_LOOKBACK_SECONDS = 30 * 86400
MATRIX_LIMIT = 24


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
def list_jobs(db: Session) -> list[SampleJob]:
    return list(db.scalars(select(SampleJob).order_by(SampleJob.id.desc())))


def get_job(db: Session, job_id: int) -> SampleJob:
    job = db.get(SampleJob, job_id)
    if job is None:
        raise AppError(ErrorCode.JOB_NOT_FOUND, detail={"job_id": job_id})
    return job


def list_samples(db: Session, job_id: int, limit: int = 20) -> tuple[list[SampleRow], int]:
    job = get_job(db, job_id)
    total = db.scalar(select(func.count(SampleRow.id)).where(SampleRow.job_id == job.id)) or 0
    rows = list(
        db.scalars(
            select(SampleRow)
            .where(SampleRow.job_id == job.id)
            .order_by(SampleRow.has_leak.desc(), SampleRow.label_time, SampleRow.id)
            .limit(limit)
        )
    )
    return rows, int(total)


def report(db: Session, job: SampleJob) -> dict:
    rows, total = list_samples(db, job.id, limit=6)
    from src.utils.serialize import sample_row_out

    result = job.result_json or {}
    return {
        "job": job_out(job),
        "leak_summary": result.get("leak_summary", {}),
        "leaks": result.get("leaks", [])[:50],
        "matrix": result.get("matrix", {}),
        "boundary_probes": result.get("boundary_probes", []),
        "run_snapshot": result.get("run_snapshot", {}),
        "failure": result.get("failure"),
        "leak_free": result.get("leak_free"),
        "sample_preview": [sample_row_out(row) for row in rows],
        "sample_total": total,
    }


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #
def _label_rows_in_range(db: Session, label_set_ids: list[int]) -> list[LabelRow]:
    return list(
        db.scalars(
            select(LabelRow)
            .where(LabelRow.label_set_id.in_(label_set_ids))
            .order_by(LabelRow.label_time, LabelRow.entity_key, LabelRow.id)
        )
    )


def create_job(db: Session, payload, user) -> SampleJob:
    features = feature_service.validate_feature_ids(db, payload.feature_ids)
    feature_service.ensure_runnable(features)
    label_sets = list(db.scalars(select(LabelSet).where(LabelSet.id.in_(payload.label_set_ids))))
    if len(label_sets) != len(set(payload.label_set_ids)):
        raise AppError(ErrorCode.LABEL_SET_NOT_FOUND, detail={"label_set_ids": payload.label_set_ids})

    range_start = parse_range(payload.range_start, "range_start") if payload.range_start else None
    range_end = parse_range(payload.range_end, "range_end") if payload.range_end else None
    if range_start and range_end and range_start >= range_end:
        raise AppError(ErrorCode.VALIDATION_FAILED, message="range_start 必须早于 range_end")

    specs = feature_service.to_specs(db, payload.feature_ids)
    boundary_policy = (
        payload.boundary_policy.value
        if payload.boundary_policy
        else _effective_boundary(features)
    )
    code = f"SJ-{utcnow().strftime('%Y%m%d%H%M%S')}"
    snapshot = {
        "engine": "pit_engine",
        "engine_version": "1.0.0",
        "label_set_ids": payload.label_set_ids,
        "label_set_codes": [item.code for item in label_sets],
        "features": feature_service.snapshot_for_job(specs),
        "boundary_policy": boundary_policy,
        "range_start": iso_z(range_start),
        "range_end": iso_z(range_end),
        "matrix_limit": MATRIX_LIMIT,
        "created_at": iso_z(utcnow()),
    }
    job = SampleJob(
        code=code,
        name=payload.name,
        kind="sample_build",
        status=JobStatus.PENDING.value,
        label_set_ids=payload.label_set_ids,
        feature_ids=payload.feature_ids,
        range_start=range_start,
        range_end=range_end,
        boundary_policy=boundary_policy,
        params_snapshot=snapshot,
        created_by=user.email,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_event("SAMPLE_JOB_CREATED", code=job.code, by=user.email, features=[f.code for f in features])
    return job


def _effective_boundary(features: Iterable[FeatureDef]) -> str:
    policies = {feature.boundary_policy for feature in features}
    if BoundaryPolicy.INCLUSIVE.value in policies:
        return BoundaryPolicy.INCLUSIVE.value
    return BoundaryPolicy.STRICT.value


# --------------------------------------------------------------------------- #
# 运行（由 Celery 任务或 seed 调用）
# --------------------------------------------------------------------------- #
def _load_events(db: Session, entity_keys: list[str], range_end) -> list[Event]:
    stmt = select(EntityEvent).where(EntityEvent.entity_key.in_(entity_keys))
    if range_end is not None:
        stmt = stmt.where(EntityEvent.event_ts <= range_end)
    rows = list(db.scalars(stmt.order_by(EntityEvent.event_ts, EntityEvent.id)))
    return normalize_events(
        [
            {
                "id": row.id,
                "entity_key": row.entity_key,
                "event_type": row.event_type,
                "ts": row.event_ts,
                "amount": float(row.amount),
            }
            for row in rows
        ]
    )


def execute_job(db: Session, job: SampleJob) -> SampleJob:
    """同步执行一次样本构建（Celery 任务与 seed 共用）。"""
    job.status = JobStatus.RUNNING.value
    job.started_at = utcnow()
    job.failure_reason = None
    db.commit()

    try:
        snapshot = job.params_snapshot or {}
        range_start = job.range_start
        range_end = job.range_end
        if range_start is None and snapshot.get("range_start"):
            range_start = parse_range(snapshot["range_start"], "range_start")
        if range_end is None and snapshot.get("range_end"):
            range_end = parse_range(snapshot["range_end"], "range_end")

        specs = feature_service.to_specs(db, list(job.feature_ids or []))
        label_rows = _label_rows_in_range(db, list(job.label_set_ids or []))
        if range_start is not None:
            label_rows = [row for row in label_rows if row.label_time >= range_start]
        if range_end is not None:
            label_rows = [row for row in label_rows if row.label_time <= range_end]
        if not label_rows:
            raise PitFailure(
                FailureReason.INSUFFICIENT_SAMPLES.value,
                "时间范围内没有任何标签样本",
                {"range_start": iso_z(range_start), "range_end": iso_z(range_end)},
            )

        entity_keys = sorted({row.entity_key for row in label_rows})
        events = _load_events(db, entity_keys, range_end)
        engine_rows = [
            EngineLabelRow(
                id=row.id,
                label_set_id=row.label_set_id,
                entity_key=row.entity_key,
                label_time=row.label_time,
                label=row.label,
            )
            for row in label_rows
        ]
        report_payload = build_report(specs, events, engine_rows, None, MATRIX_LIMIT)

        db.execute(delete(SampleRow).where(SampleRow.job_id == job.id))
        for sample in report_payload.pop("_samples", None) or _rebuild_samples(specs, events, engine_rows):
            db.add(
                SampleRow(
                    job_id=job.id,
                    label_row_id=sample["label_row_id"],
                    label_set_id=sample["label_set_id"],
                    entity_key=sample["entity_key"],
                    label_time=parse_range(sample["label_time"], "label_time"),
                    label=sample["label"],
                    features_json=sample["features"],
                    leak_flags=sample["leak_flags"],
                    has_leak=sample["has_leak"],
                    no_event=sample["no_event"],
                )
            )

        job.sample_count = report_payload["sample_count"]
        job.leak_count = report_payload["leak_summary"]["leak_count"]
        job.status = JobStatus.COMPLETED.value
        job.finished_at = utcnow()
        job.result_json = {
            **report_payload,
            "run_snapshot": {
                "features": feature_service.snapshot_for_job(specs),
                "boundary_policy": _effective_boundary(
                    feature_service.validate_feature_ids(db, list(job.feature_ids or []))
                ),
                "engine": "pit_engine",
                "executed_at": iso_z(utcnow()),
                "label_rows": len(engine_rows),
                "events_loaded": len(events),
            },
        }
        db.commit()
        log_event(
            "SAMPLE_JOB_COMPLETED",
            code=job.code,
            samples=job.sample_count,
            leaks=job.leak_count,
        )
        return job
    except PitFailure as failure:
        job.status = JobStatus.FAILED.value
        job.failure_reason = failure.reason
        job.finished_at = utcnow()
        job.sample_count = 0
        job.leak_count = 0
        job.result_json = {
            "failure": {
                "reason": failure.reason,
                "message": failure.message,
                "detail": failure.detail,
            },
            "leak_summary": {"leak_count": 0, "by_feature": []},
            "leaks": [],
            "matrix": {"features": [], "samples": [], "total_samples": 0, "shown_samples": 0},
            "boundary_probes": [],
            "leak_free": False,
        }
        db.commit()
        log_event("SAMPLE_JOB_FAILED", code=job.code, reason=failure.reason, message=failure.message)
        return job


def _rebuild_samples(specs, events, engine_rows):
    """build_report 只返回矩阵（截断）；落库要全量样本，所以再算一次纯样本。"""
    from src.services.pit_engine import build_samples

    built = build_samples(specs, events, engine_rows, None)
    return built["samples"]


def run_job_by_id(db: Session, job_id: int) -> SampleJob:
    job = get_job(db, job_id)
    return execute_job(db, job)


# --------------------------------------------------------------------------- #
# 失败态辅助：只做参数校验、不落样本（用于 API 400）
# --------------------------------------------------------------------------- #
def validate_range(raw_start, raw_end):
    start = parse_range(raw_start, "range_start") if raw_start else None
    end = parse_range(raw_end, "range_end") if raw_end else None
    if start and end and start >= end:
        raise AppError(ErrorCode.VALIDATION_FAILED, message="range_start 必须早于 range_end")
    return start, end


def lookback_floor(range_start, seconds: int = MAX_LOOKBACK_SECONDS):
    if range_start is None:
        return None
    return range_start - timedelta(seconds=seconds)


def label_time_iso(value) -> str | None:
    return iso_ms_z(value)
