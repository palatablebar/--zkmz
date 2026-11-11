"""Backfill task lifecycle: create → run (agg_engine) → full/incremental 一致性报告。

口径（修正版，替代旧的「范围中点切事件」实现）：

* 基准 = 上一次**成功**运行固定下来的事件台账水位 ``baseline_cutoff_seq``；
  首次运行没有基准，全量结果同时作为基准落库。
* 事件状态由 append-only 台账（``event_ledger``）按 seq 重放得到：基准重放包含
  范围起点之前的完整窗口历史，不再把同一次事件读取按时间中点切开。
* 增量 = 基准事件状态 + 基准水位之后到达的投递（新增/更正/撤销）；同一
  ``delivery_id`` 的重复投递在台账层只生效一次。
* 新批次未对平（重复投递 / 撤销缺失 / 改写基准内事件）时**保留上一次结果**：
  任务置 ``failed``，checksum、invariant 与 result_json 均不覆盖，对账明细写入
  ``last_reconciliation`` 说明每条被忽略、撤销或替换的记录影响了哪些样本。
* 一致性报告整体落 ``backfill_task.result_json``（checksum、差异样本数、
  首个差异位置、原因分类、台账影响分析、负例对照）。
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import BackfillStatus
from src.constants.error_codes import AppError, ErrorCode
from src.models import BackfillTask, EventLedger, LabelRow
from src.services import agg_engine, event_ingest_service
from src.services.pit_engine import LabelRow as EngineLabelRow, PitFailure, parse_range
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

    code = f"BF-{utcnow().strftime('%Y%m%d%H%M%S')}"
    task = BackfillTask(
        code=code,
        name=payload.name,
        mode=payload.mode.value if hasattr(payload.mode, "value") else str(payload.mode),
        status=BackfillStatus.PENDING.value,
        range_start=range_start,
        range_end=range_end,
        # base_watermark 仅为兼容旧报告保留；新逻辑以 baseline_cutoff_seq 为准
        base_watermark=None,
        baseline_cutoff_seq=None,
        baseline_event_count=None,
        feature_ids=payload.feature_ids or [],
        created_by=user.email,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_event("BACKFILL_CREATED", code=task.code, mode=task.mode, by=user.email)
    return task


def execute_backfill(db: Session, task: BackfillTask) -> BackfillTask:
    previous_result = task.result_json
    previous_full = task.full_checksum
    previous_inc = task.incremental_checksum
    previous_invariant = task.invariant_hold
    previous_cutoff = task.baseline_cutoff_seq
    previous_base_count = task.baseline_event_count

    task.status = BackfillStatus.RUNNING.value
    task.started_at = utcnow()
    db.commit()
    try:
        range_start = parse_range(task.range_start, "range_start")
        range_end = parse_range(task.range_end, "range_end")
        label_rows = list(
            db.scalars(
                select(LabelRow)
                .where(LabelRow.label_time >= range_start, LabelRow.label_time <= range_end)
                .order_by(LabelRow.id)
            )
        )
        if not label_rows:
            raise PitFailure("insufficient_samples", "回填范围内没有任何标签样本", {})
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

        # 台账是事件状态的唯一来源；窗口历史（range_start 之前 30 天）天然包含在
        # 重放结果里，范围参数不再参与事件裁切。
        ledger_entries = event_ingest_service.load_ledger(db)
        if not ledger_entries:
            raise PitFailure("insufficient_samples", "事件台账为空，没有可回填的事件", {})
        current_cutoff = max(entry.seq for entry in ledger_entries)
        baseline_cutoff = task.baseline_cutoff_seq

        report = agg_engine.run_backfill(
            engine_rows,
            ledger_entries,
            baseline_cutoff=baseline_cutoff,
            current_cutoff=current_cutoff,
            range_start=range_start,
            range_end=range_end,
        )

        if not report["aligned"]:
            return _handle_misaligned(
                db,
                task,
                report,
                previous_result,
                previous_full,
                previous_inc,
                previous_invariant,
                previous_cutoff,
                previous_base_count,
            )

        task.full_checksum = report["full"]["checksum"]
        task.incremental_checksum = report["incremental"]["checksum"]
        task.invariant_hold = bool(report["invariant_hold"])
        task.status = BackfillStatus.COMPLETED.value
        task.finished_at = utcnow()
        # 成功后把当前水位固定为下一次增量的基准
        task.baseline_cutoff_seq = current_cutoff
        task.baseline_event_count = report["scoped_event_count"]
        task.result_json = {
            **report,
            "mode": task.mode,
            "executed_at": iso_z(utcnow()),
            "engine": "agg_engine",
            "feature_ids": task.feature_ids,
            "baseline": {
                "cutoff_seq": baseline_cutoff,
                "event_count": report["base_event_count"],
                "first_run": baseline_cutoff is None,
            },
        }
        db.commit()
        log_event(
            "BACKFILL_COMPLETED",
            code=task.code,
            equal=report["equal"],
            samples=report["sample_count"],
            diff=report["diff_sample_count"],
            baseline_cutoff=baseline_cutoff,
            current_cutoff=current_cutoff,
        )
        return task
    except PitFailure as failure:
        task.status = BackfillStatus.FAILED.value
        task.finished_at = utcnow()
        # 数据不足类失败同样不覆盖已有成功结果，只追加 last_failure 诊断
        task.full_checksum = previous_full
        task.incremental_checksum = previous_inc
        task.invariant_hold = previous_invariant
        task.baseline_cutoff_seq = previous_cutoff
        task.baseline_event_count = previous_base_count
        task.result_json = {
            **(previous_result or {}),
            "last_failure": {
                "reason": failure.reason,
                "message": failure.message,
                "detail": failure.detail,
                "at": iso_z(utcnow()),
            },
        }
        db.commit()
        log_event("BACKFILL_FAILED", code=task.code, reason=failure.reason)
        return task


def _handle_misaligned(
    db: Session,
    task: BackfillTask,
    report: dict,
    previous_result,
    previous_full,
    previous_inc,
    previous_invariant,
    previous_cutoff,
    previous_base_count,
) -> BackfillTask:
    """新批次未对平：保留旧结果，只落对账诊断，任务标记失败等待上游处理。"""
    reconciliation = report["reconciliation"]
    record = {
        "at": iso_z(utcnow()),
        "reason": "batch_not_aligned",
        "message": "新投递批次未与基准对平，已保留上一次回填结果，本次结果不落库",
        "issue_count": reconciliation["issue_count"],
        "issues": reconciliation["issues"],
        "impact_summary": report["impact_summary"],
        "ledger_impact": report["ledger_impact"],
        "baseline_cutoff_seq": previous_cutoff,
        "current_cutoff_seq": report["current_cutoff_seq"],
    }
    task.status = BackfillStatus.FAILED.value
    task.finished_at = utcnow()
    task.full_checksum = previous_full
    task.incremental_checksum = previous_inc
    task.invariant_hold = previous_invariant
    task.baseline_cutoff_seq = previous_cutoff
    task.baseline_event_count = previous_base_count
    task.result_json = {
        **(previous_result or {}),
        "last_reconciliation": record,
    }
    db.commit()
    log_event(
        "BACKFILL_MISALIGNED",
        code=task.code,
        issues=reconciliation["issue_count"],
        retained_previous=previous_result is not None,
    )
    return task


def run_backfill_by_id(db: Session, backfill_id: int) -> BackfillTask:
    task = get_backfill(db, backfill_id)
    return execute_backfill(db, task)


def default_range(db: Session) -> dict:
    """UI「发起 30 天回填」的默认范围（基于演示事件的最新时间）."""
    latest = db.scalar(select(EventLedger.event_ts).order_by(EventLedger.event_ts.desc()).limit(1))
    if latest is None:
        now = utcnow()
        return {"start": iso_z(now - timedelta(days=30)), "end": iso_z(now)}
    return {"start": iso_z(latest - timedelta(days=30)), "end": iso_z(latest)}


def out(task: BackfillTask, with_report: bool = False) -> dict:
    payload = backfill_out(task)
    if not with_report:
        payload.pop("report", None)
    return payload
