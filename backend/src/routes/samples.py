"""Sample job router — analyst/owner may create + run, viewer is read-only."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import sample_controller
from src.middlewares.rbac import require_reader, require_sample_editor
from src.schemas.sample import SampleJobCreate

router = APIRouter(prefix="/sample-jobs", tags=["samples"])


@router.get("")
def list_jobs(db: Session = Depends(get_db), user=Depends(require_reader)):
    return sample_controller.list_jobs(db, user)


@router.post("", status_code=201)
def create_job(
    payload: SampleJobCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_sample_editor),
):
    return sample_controller.create_job(db, user, payload, request)


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), user=Depends(require_reader)):
    return sample_controller.get_job(db, user, job_id)


@router.get("/{job_id}/report")
def get_report(job_id: int, db: Session = Depends(get_db), user=Depends(require_reader)):
    return sample_controller.get_report(db, user, job_id)


@router.get("/{job_id}/samples")
def get_samples(job_id: int, limit: int = 20, db: Session = Depends(get_db), user=Depends(require_reader)):
    return sample_controller.get_samples(db, user, job_id, limit)


@router.post("/{job_id}/run")
def run_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_sample_editor),
):
    return sample_controller.run_job(db, user, job_id, request)
