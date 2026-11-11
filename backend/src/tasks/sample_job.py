"""Celery task: build samples for one sample job with the PIT engine."""
from src.config.celery_app import celery_app
from src.config.database import SessionLocal
from src.services import sample_service
from src.utils.logger import log_event

TASK_NAME = "featpoint.run_sample_job"


@celery_app.task(name=TASK_NAME, bind=True, max_retries=1)
def run_sample_job(self, job_id: int) -> dict:
    db = SessionLocal()
    try:
        job = sample_service.run_job_by_id(db, job_id)
        return {"job_id": job.id, "status": job.status, "samples": job.sample_count, "leaks": job.leak_count}
    finally:
        db.close()


def dispatch_sample_job(job_id: int, actor: str) -> dict:
    """Enqueue the Celery task; fall back to an inline run if the broker is down."""
    try:
        async_result = run_sample_job.apply_async(args=[job_id], queue="featpoint")
        log_event("SAMPLE_JOB_QUEUED", job_id=job_id, task_id=async_result.id, actor=actor)
        return {"job_id": job_id, "task_id": async_result.id, "queued": True, "status": "running"}
    except Exception as exc:  # pragma: no cover - broker failure path
        log_event("SAMPLE_JOB_INLINE_FALLBACK", job_id=job_id, reason=str(exc))
        db = SessionLocal()
        try:
            job = sample_service.run_job_by_id(db, job_id)
            return {
                "job_id": job_id,
                "task_id": None,
                "queued": False,
                "status": job.status,
                "samples": job.sample_count,
                "leaks": job.leak_count,
            }
        finally:
            db.close()
