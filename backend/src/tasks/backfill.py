"""Celery task: run one backfill consistency check with the aggregate engine."""
from src.config.celery_app import celery_app
from src.config.database import SessionLocal
from src.services import backfill_service
from src.utils.logger import log_event

TASK_NAME = "featpoint.run_backfill"


@celery_app.task(name=TASK_NAME, bind=True, max_retries=1)
def run_backfill(self, backfill_id: int) -> dict:
    db = SessionLocal()
    try:
        task = backfill_service.run_backfill_by_id(db, backfill_id)
        report = task.result_json or {}
        return {
            "backfill_id": task.id,
            "status": task.status,
            "equal": report.get("equal"),
            "diff_sample_count": report.get("diff_sample_count"),
        }
    finally:
        db.close()


def dispatch_backfill(backfill_id: int, actor: str) -> dict:
    try:
        async_result = run_backfill.apply_async(args=[backfill_id], queue="featpoint")
        log_event("BACKFILL_QUEUED", backfill_id=backfill_id, task_id=async_result.id, actor=actor)
        return {"backfill_id": backfill_id, "task_id": async_result.id, "queued": True, "status": "running"}
    except Exception as exc:  # pragma: no cover - broker failure path
        log_event("BACKFILL_INLINE_FALLBACK", backfill_id=backfill_id, reason=str(exc))
        db = SessionLocal()
        try:
            task = backfill_service.run_backfill_by_id(db, backfill_id)
            return {
                "backfill_id": backfill_id,
                "task_id": None,
                "queued": False,
                "status": task.status,
                "equal": (task.result_json or {}).get("equal"),
            }
        finally:
            db.close()
