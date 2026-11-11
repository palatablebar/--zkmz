"""Sample job handlers (wired by app/routes/samples.py)."""
from src.middlewares import quota as quota_middleware
from src.middlewares.audit_logger import record
from src.schemas.common import page
from src.services import sample_service
from src.utils.serialize import job_out, sample_row_out


def list_jobs(db, user) -> dict:
    items = [job_out(job) for job in sample_service.list_jobs(db)]
    return page(items, len(items))


def create_job(db, user, payload, request=None) -> dict:
    job = sample_service.create_job(db, payload, user)
    record(
        request,
        "job_create",
        "sample_job",
        job.id,
        after={"code": job.code, "features": job.feature_ids, "boundary": job.boundary_policy},
    )
    return job_out(job)


def get_job(db, user, job_id: int) -> dict:
    job = sample_service.get_job(db, job_id)
    return {"job": job_out(job), "report": sample_service.report(db, job)}


def get_report(db, user, job_id: int) -> dict:
    job = sample_service.get_job(db, job_id)
    return sample_service.report(db, job)


def get_samples(db, user, job_id: int, limit: int = 20) -> dict:
    rows, total = sample_service.list_samples(db, job_id, limit=min(max(limit, 1), 200))
    return {"items": [sample_row_out(row) for row in rows], "total": total}


def run_job(db, user, job_id: int, request=None) -> dict:
    job = sample_service.get_job(db, job_id)
    quota_middleware.consume_daily_quota(db, user, "sample_job_run")
    job.status = "running"
    db.commit()
    record(request, "job_run", "sample_job", job.id, after={"code": job.code})
    from src.tasks.sample_job import dispatch_sample_job

    return dispatch_sample_job(job.id, user.email)
