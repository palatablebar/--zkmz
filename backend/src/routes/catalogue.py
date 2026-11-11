"""Read-only catalogue router: label sets / events / audit / overview."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import catalogue_controller
from src.middlewares.rbac import require_reader

router = APIRouter(tags=["catalogue"])


@router.get("/label-sets")
def list_label_sets(db: Session = Depends(get_db), user=Depends(require_reader)):
    return catalogue_controller.list_label_sets(db, user)


@router.get("/events")
def list_events(
    limit: int = 60,
    offset: int = 0,
    event_type: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_reader),
):
    return catalogue_controller.list_events(db, user, limit, offset, event_type)


@router.get("/audit-logs")
def list_audits(
    limit: int = 30,
    feature_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_reader),
):
    return catalogue_controller.list_audits(db, user, limit, feature_id)


@router.get("/overview")
def overview(db: Session = Depends(get_db), user=Depends(require_reader)):
    return catalogue_controller.overview(db, user)
