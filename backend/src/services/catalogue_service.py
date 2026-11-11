"""Read-only catalogue: account events, label sets, audit trail, /meta payload."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    AggregateKind,
    BackfillMode,
    BoundaryPolicy,
    EventType,
    FeatureStatus,
    JobStatus,
    LeakKind,
    Role,
    ROLE_LABELS,
)
from src.constants.recipes import MARGIN_NOTES, OPERATION_STEPS
from src.models import AuditLog, EntityEvent, FeatureDef, LabelRow, LabelSet, SampleJob
from src.services import backfill_service
from src.utils.serialize import audit_out, event_out
from src.utils.timefmt import iso_z


def list_events(db: Session, limit: int = 60, offset: int = 0, event_type: str | None = None) -> dict:
    stmt = select(EntityEvent)
    count_stmt = select(func.count(EntityEvent.id))
    if event_type:
        stmt = stmt.where(EntityEvent.event_type == event_type)
        count_stmt = count_stmt.where(EntityEvent.event_type == event_type)
    total = db.scalar(count_stmt) or 0
    rows = list(
        db.scalars(stmt.order_by(EntityEvent.event_ts.desc(), EntityEvent.id.desc()).limit(limit).offset(offset))
    )
    type_counts = dict(
        db.execute(
            select(EntityEvent.event_type, func.count(EntityEvent.id)).group_by(EntityEvent.event_type)
        ).all()
    )
    amount_sum = db.scalar(select(func.coalesce(func.sum(EntityEvent.amount), 0))) or 0
    entity_count = db.scalar(select(func.count(func.distinct(EntityEvent.entity_key)))) or 0
    return {
        "items": [event_out(row) for row in rows],
        "total": int(total),
        "summary": {
            "by_type": type_counts,
            "amount_sum": float(amount_sum),
            "entity_count": int(entity_count),
        },
    }


def list_label_sets(db: Session) -> list[dict]:
    sets = list(db.scalars(select(LabelSet).order_by(LabelSet.id)))
    out: list[dict] = []
    for label_set in sets:
        stats = db.execute(
            select(
                func.count(LabelRow.id),
                func.count(func.distinct(LabelRow.entity_key)),
                func.coalesce(func.sum(LabelRow.label), 0),
                func.min(LabelRow.label_time),
                func.max(LabelRow.label_time),
            ).where(LabelRow.label_set_id == label_set.id)
        ).one()
        out.append(
            {
                "id": label_set.id,
                "code": label_set.code,
                "name": label_set.name,
                "description": label_set.description,
                "sample_count": int(stats[0] or 0),
                "entity_count": int(stats[1] or 0),
                "label_positive": int(stats[2] or 0),
                "first_label_time": iso_z(stats[3]),
                "last_label_time": iso_z(stats[4]),
            }
        )
    return out


def list_audits(db: Session, limit: int = 30, feature_id: int | None = None) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if feature_id is not None:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == "feature_def", AuditLog.entity_id == feature_id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
    return [audit_out(row) for row in db.scalars(stmt)]


def overview(db: Session) -> dict:
    """登录后的工艺卡封面数据：各实体计数与泄漏总览。"""
    features = list(db.scalars(select(FeatureDef).order_by(FeatureDef.id)))
    jobs = list(db.scalars(select(SampleJob).order_by(SampleJob.id.desc()).limit(6)))
    return {
        "features": [
            {
                "id": f.id,
                "code": f.code,
                "window_label": f.window_label,
                "boundary_policy": f.boundary_policy,
                "status": f.status,
                "version": f.version,
            }
            for f in features
        ],
        "jobs": [
            {
                "id": j.id,
                "code": j.code,
                "status": j.status,
                "sample_count": j.sample_count,
                "leak_count": j.leak_count,
            }
            for j in jobs
        ],
        "counts": {
            "features": len(features),
            "events": int(db.scalar(select(func.count(EntityEvent.id))) or 0),
            "label_rows": int(db.scalar(select(func.count(LabelRow.id))) or 0),
            "jobs": int(db.scalar(select(func.count(SampleJob.id))) or 0),
        },
    }


def meta(db: Session) -> dict:
    return {
        "app": "FeatPoint",
        "short": "featpoint",
        "client": "岚舟科技 · 风控算法组",
        "engine": {"pit": "pit_engine", "agg": "agg_engine", "version": "1.0.0"},
        "roles": [{"value": r.value, "label": ROLE_LABELS[r]} for r in Role],
        "boundary_policies": [{"value": b.value, "label": b.value} for b in BoundaryPolicy],
        "aggregates": [{"value": a.value, "label": a.value} for a in AggregateKind],
        "event_types": [{"value": e.value, "label": e.value} for e in EventType],
        "feature_statuses": [{"value": s.value, "label": s.value} for s in FeatureStatus],
        "job_statuses": [{"value": s.value, "label": s.value} for s in JobStatus],
        "leak_kinds": [{"value": k.value, "label": k.value} for k in LeakKind],
        "backfill_modes": [{"value": m.value, "label": m.value} for m in BackfillMode],
        "operation_steps": OPERATION_STEPS,
        "margin_notes": MARGIN_NOTES,
        "default_backfill_range": backfill_service.default_range(db),
        "limits": {
            "rate_window_seconds": settings.RATE_WINDOW_SECONDS,
            "rate_window_max": settings.RATE_WINDOW_MAX,
            "daily_run_quota": settings.DAILY_RUN_QUOTA,
        },
    }
