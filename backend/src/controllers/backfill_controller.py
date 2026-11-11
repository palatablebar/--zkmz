"""Backfill handlers (wired by app/routes/backfills.py)."""
from src.middlewares import quota as quota_middleware
from src.middlewares.audit_logger import record
from src.schemas.common import page
from src.services import backfill_service


def list_backfills(db, user) -> dict:
    items = [backfill_service.out(task) for task in backfill_service.list_backfills(db)]
    return page(items, len(items))


def create_backfill(db, user, payload, request=None) -> dict:
    task = backfill_service.create_backfill(db, payload, user)
    record(
        request,
        "backfill_create",
        "backfill_task",
        task.id,
        after={"code": task.code, "mode": task.mode},
    )
    return backfill_service.out(task, with_report=True)


def get_backfill(db, user, backfill_id: int) -> dict:
    task = backfill_service.get_backfill(db, backfill_id)
    return backfill_service.out(task, with_report=True)


def run_backfill(db, user, backfill_id: int, request=None) -> dict:
    task = backfill_service.get_backfill(db, backfill_id)
    quota_middleware.consume_daily_quota(db, user, "backfill_run")
    record(request, "backfill_run", "backfill_task", task.id, after={"code": task.code})
    from src.tasks.backfill import dispatch_backfill

    return dispatch_backfill(task.id, user.email)
