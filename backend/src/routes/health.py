"""Health + meta (both public: compose healthcheck and the login page shell)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import catalogue_controller
from src.models import EntityEvent, FeatureDef, LabelRow, SampleJob
from src.utils.timefmt import iso_z, utcnow

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    checks = {"db": False, "tables": False}
    counts = {}
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = True
        counts = {
            "features": int(db.scalar(select(func.count(FeatureDef.id))) or 0),
            "events": int(db.scalar(select(func.count(EntityEvent.id))) or 0),
            "label_rows": int(db.scalar(select(func.count(LabelRow.id))) or 0),
            "jobs": int(db.scalar(select(func.count(SampleJob.id))) or 0),
        }
        checks["tables"] = counts["events"] >= 0
    except Exception:
        checks["db"] = False
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "service": "featpoint-backend", "checks": checks, "counts": counts,
            "time": iso_z(utcnow())}


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    return catalogue_controller.meta(db)
