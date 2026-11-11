"""Backfill task lifecycle: create → run (agg_engine) → full/incremental 一致性报告。

* 基准水位（base_watermark）= 范围中点：前半段事件算「基准快照」，后半段算
  「新增事件」，增量重算 = 基准 + 新增合并。
* 一致性报告整体落 ``backfill_task.result_json``（checksum、差异样本数、
  首个差异位置、原因分类、负例对照）。
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import BackfillMode, BackfillStatus
from src.constants.error_codes import AppError, ErrorCode
from src.models import BackfillTask, EntityEvent, LabelRow
from src.services import agg_engine
from src.services.pit_engine import LabelRow as EngineLabelRow, PitFailure, normalize_events, parse_range
from src.utils.logger import log_event
from src.utils.serialize import backfill_out
from src.utils.timefmt import iso_z, utcnow

MAX_LOOKBACK_SECONDS = 30 * 86400


def list_backfills(db: Session) -> list[BackfillTask]:
    return list(db.scalars(select(BackfillTask).order_by(BackfillTask.id.desc())))


def get_backfill(db: Session, backfill_id: int) -> BackfillTask:
    task = db.get(BackfillTask, backfill_id)
    if task is None:
        raise AppError(ErrorCode.BACKFILL_NOT_FOUND, detail={"backfill_id": backfill_id})
    return task


def create_backfill(db: Session, payload, user) -> BackfillTask:
    try:
        range_start = parse_range(payload.range_start, "range_start")
        range_end = parse_range(payload.range_end, "range_end")
    except PitFailure as failure:
        raise AppError(ErrorCode.BAD_TIMESTAMP, message=failure.message, detail=failure.detail) from failure
    if range_start >= range_end:
        raise AppError(ErrorCode.BACKFILL_RANGE_INVALID, message="range_start 必须早于 range_end")
    if (range_end - range_start) > timedelta(days=180):
        raise AppError(ErrorCode.BACKFILL_RANGE_INVALID, message="单次回填范围不能超过 180 天")

    watermark = range_start + (range_end - range_start) / 2
    code = f"BF-{utcnow().strftime('%Y%m%d%H%M%S')}"
    task = BackfillTask(
        code=code,
        name=payload.name,
        mode=payload.mode.value if hasattr(payload.mode, "value") else str(payload.mode),
        status=BackfillStatus.PENDING.value,
        range_start=range_start,
        range_end=range_end,
        base_watermark=watermark,
        feature_ids=payload.feature_ids or [],
        created_by=user.email,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_event("BACKFILL_CREATED", code=task.code, mode=task.mode, by=user.email)
    return task


def execute_backfill(db: Session, task: BackfillTask) -> BackfillTask:
    task.status = BackfillStatus.RUNNING.value
    task.started_at = utcnow()
    db.commit()
    try:
        range_start = parse_range(task.range_start, "range_start")
        range_end = parse_range(task.range_end, "range_end")
        watermark = parse_range(task.base_watermark, "base_watermark")
        label_rows = list(
            db.scalars(
                select(LabelRow)
                .where(LabelRow.label_time >= range_start, LabelRow.label_time <= range_end)
                .order_by(LabelRow.id)
            )
        )
        if not label_rows:
            raise PitFailure("insufficient_samples", "回填范围内没有任何标签样本", {})
        entity_keys = sorted({row.entity_key for row in label_rows})
        floor = range_start - timedelta(seconds=MAX_LOOKBACK_SECONDS)
        events = list(
            db.scalars(
                select(EntityEvent)
                .where(
                    EntityEvent.entity_key.in_(entity_keys),
                    EntityEvent.event_ts >= floor,
                    EntityEvent.event_ts <= range_end,
                )
                .order_by(EntityEvent.event_ts, EntityEvent.id)
            )
        )
        normalized = normalize_events(
            [
                {
                    "id": row.id,
                    "entity_key": row.entity_key,
                    "event_type": row.event_type,
                    "ts": row.event_ts,
                    "amount": float(row.amount),
                }
                for row in events
            ]
        )
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
        report = agg_engine.run_backfill(
            engine_rows,
            normalized,
            watermark,
            range_start=range_start,
            range_end=range_end,
        )
        task.full_checksum = report["full"]["checksum"]
        task.incremental_checksum = report["incremental"]["checksum"]
        task.invariant_hold = bool(report["invariant_hold"])
        task.status = BackfillStatus.COMPLETED.value
        task.finished_at = utcnow()
        task.result_json = {
            **report,
            "mode": task.mode,
            "executed_at": iso_z(utcnow()),
            "engine": "agg_engine",
            "feature_ids": task.feature_ids,
        }
        db.commit()
        log_event(
            "BACKFILL_COMPLETED",
            code=task.code,
            equal=report["equal"],
            samples=report["sample_count"],
            diff=report["diff_sample_count"],
        )
        return task
    except PitFailure as failure:
        task.status = BackfillStatus.FAILED.value
        task.finished_at = utcnow()
        task.result_json = {
            "failure": {"reason": failure.reason, "message": failure.message, "detail": failure.detail},
            "equal": False,
            "invariant_hold": False,
        }
        db.commit()
        log_event("BACKFILL_FAILED", code=task.code, reason=failure.reason)
        return task


def run_backfill_by_id(db: Session, backfill_id: int) -> BackfillTask:
    task = get_backfill(db, backfill_id)
    return execute_backfill(db, task)


def default_range(db: Session) -> dict:
    """UI「发起 30 天回填」的默认范围（基于演示事件的最新时间）."""
    latest = db.scalar(select(EntityEvent.event_ts).order_by(EntityEvent.event_ts.desc()).limit(1))
    if latest is None:
        now = utcnow()
        return {"start": iso_z(now - timedelta(days=30)), "end": iso_z(now)}
    return {"start": iso_z(latest - timedelta(days=30)), "end": iso_z(latest)}


def out(task: BackfillTask, with_report: bool = False) -> dict:
    payload = backfill_out(task)
    if not with_report:
        payload.pop("report", None)
    return payload
