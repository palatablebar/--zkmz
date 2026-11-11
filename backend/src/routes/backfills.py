"""Backfill router — owner-only create/run, everyone reads the report."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import backfill_controller
from src.middlewares.rbac import require_owner, require_reader
from src.schemas.backfill import BackfillCreate

router = APIRouter(prefix="/backfills", tags=["backfills"])


@router.get("")
def list_backfills(db: Session = Depends(get_db), user=Depends(require_reader)):
    return backfill_controller.list_backfills(db, user)


@router.post("", status_code=201)
def create_backfill(
    payload: BackfillCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_owner),
):
    return backfill_controller.create_backfill(db, user, payload, request)


@router.get("/{backfill_id}")
def get_backfill(backfill_id: int, db: Session = Depends(get_db), user=Depends(require_reader)):
    return backfill_controller.get_backfill(db, user, backfill_id)


@router.post("/{backfill_id}/run")
def run_backfill(
    backfill_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_owner),
):
    return backfill_controller.run_backfill(db, user, backfill_id, request)
