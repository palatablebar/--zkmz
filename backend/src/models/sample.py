"""Sample job (parameter snapshot) + materialised sample rows."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class SampleJob(Base):
    __tablename__ = "sample_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="sample_build")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    label_set_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    feature_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    boundary_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="strict")
    params_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leak_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="system")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SampleRow(Base):
    """One materialised sample: label + the feature JSON computed by the PIT engine."""

    __tablename__ = "sample_row"
    __table_args__ = (UniqueConstraint("job_id", "label_row_id", name="uq_sample_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("sample_job.id"), nullable=False, index=True)
    label_row_id: Mapped[int] = mapped_column(ForeignKey("label_row.id"), nullable=False, index=True)
    label_set_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_key: Mapped[str] = mapped_column(String(48), nullable=False)
    label_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    leak_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    has_leak: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    no_event: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
