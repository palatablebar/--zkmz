"""Row → API payload serialisers (single place, keeps controllers thin)."""
from src.constants.enums import ROLE_LABELS
from src.utils.timefmt import iso_z

AGG_LABEL = {
    "sum": "sum(amount)",
    "count": "count(*)",
    "max": "max(amount)",
    "last": "last(amount)",
    "recency_days": "recency_days",
}

WINDOW_SQL = {
    "strict": {"left": "]", "right": ")", "op": "ts < label_time"},
    "inclusive": {"left": "(", "right": "]", "op": "ts <= label_time"},
}


def feature_dsl(feature) -> str:
    """Human readable DSL preview (also rendered as the recipe card body)."""
    left = "[" if feature.boundary_policy == "strict" else "("
    right = ")" if feature.boundary_policy == "strict" else "]"
    filter_text = f"event_type={feature.event_type or 'any'}"
    if feature.amount_min is not None:
        filter_text += f", amount>={float(feature.amount_min):g}"
    agg = AGG_LABEL.get(feature.aggregate_kind, feature.aggregate_kind)
    return (
        f"entity(account) WHERE {filter_text}\n"
        f"  WINDOW {left}label_time - {feature.window_label}, label_time{right}\n"
        f"  AGG {agg} AS {feature.code}"
    )


def user_out(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
    }


def feature_out(feature) -> dict:
    return {
        "id": feature.id,
        "code": feature.code,
        "name": feature.name,
        "description": feature.description,
        "event_type": feature.event_type,
        "amount_min": float(feature.amount_min) if feature.amount_min is not None else None,
        "window_seconds": feature.window_seconds,
        "window_label": feature.window_label,
        "boundary_policy": feature.boundary_policy,
        "aggregate_kind": feature.aggregate_kind,
        "status": feature.status,
        "version": feature.version,
        "owner_id": feature.owner_id,
        "published_at": iso_z(feature.published_at),
        "updated_at": iso_z(feature.updated_at),
        "dsl": feature_dsl(feature),
    }


def feature_version_out(version) -> dict:
    return {
        "id": version.id,
        "version_no": version.version_no,
        "change_note": version.change_note,
        "changed_by": version.changed_by,
        "snapshot": version.snapshot or {},
        "created_at": iso_z(version.created_at),
    }


def job_out(job) -> dict:
    snapshot = job.params_snapshot or {}
    result = job.result_json or {}
    leak_summary = result.get("leak_summary")
    return {
        "id": job.id,
        "code": job.code,
        "name": job.name,
        "status": job.status,
        "label_set_ids": job.label_set_ids or [],
        "feature_ids": job.feature_ids or [],
        "range_start": iso_z(job.range_start),
        "range_end": iso_z(job.range_end),
        "boundary_policy": job.boundary_policy,
        "sample_count": job.sample_count,
        "leak_count": job.leak_count,
        "failure_reason": job.failure_reason,
        "created_by": job.created_by,
        "started_at": iso_z(job.started_at),
        "finished_at": iso_z(job.finished_at),
        "created_at": iso_z(job.created_at),
        "params_snapshot": {
            "label_set_codes": snapshot.get("label_set_codes", []),
            "range_start": snapshot.get("range_start"),
            "range_end": snapshot.get("range_end"),
            "features": snapshot.get("features", []),
            "engine": snapshot.get("engine"),
            "matrix_limit": snapshot.get("matrix_limit"),
        },
        "leak_summary": leak_summary,
        "leak_free": result.get("leak_free"),
    }


def backfill_out(task) -> dict:
    report = task.result_json or None
    return {
        "id": task.id,
        "code": task.code,
        "name": task.name,
        "mode": task.mode,
        "status": task.status,
        "range_start": iso_z(task.range_start),
        "range_end": iso_z(task.range_end),
        "base_watermark": iso_z(task.base_watermark),
        "feature_ids": task.feature_ids or [],
        "full_checksum": task.full_checksum,
        "incremental_checksum": task.incremental_checksum,
        "invariant_hold": task.invariant_hold,
        "created_by": task.created_by,
        "started_at": iso_z(task.started_at),
        "finished_at": iso_z(task.finished_at),
        "created_at": iso_z(task.created_at),
        "report": report,
    }


def audit_out(row) -> dict:
    return {
        "id": row.id,
        "actor_email": row.actor_email,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "created_at": iso_z(row.created_at),
        "after_json": row.after_json,
    }


def label_row_out(row) -> dict:
    return {
        "id": row.id,
        "label_set_id": row.label_set_id,
        "entity_key": row.entity_key,
        "label_time": iso_z(row.label_time),
        "label": row.label,
    }


def event_out(row) -> dict:
    return {
        "id": row.id,
        "entity_key": row.entity_key,
        "event_type": row.event_type,
        "event_ts": iso_z(row.event_ts),
        "amount": float(row.amount),
        "channel": row.channel,
        "source_ref": row.source_ref,
    }


def sample_row_out(row) -> dict:
    return {
        "id": row.id,
        "label_row_id": row.label_row_id,
        "label_set_id": row.label_set_id,
        "entity_key": row.entity_key,
        "label_time": iso_z(row.label_time),
        "label": row.label,
        "features": row.features_json,
        "leak_flags": row.leak_flags,
        "has_leak": row.has_leak,
        "no_event": row.no_event,
    }


def boundary_label(policy: str) -> str:
    return "strict（右端开区间）" if policy == "strict" else "inclusive（右端含标签时刻）"
