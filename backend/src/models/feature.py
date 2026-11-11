"""Feature definition + immutable version snapshots."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class FeatureDef(Base):
    __tablename__ = "feature_def"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="account")
    event_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    amount_min: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    window_label: Mapped[str] = mapped_column(String(16), nullable=False)
    boundary_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="strict")
    aggregate_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="sum")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeatureVersion(Base):
    """Written on every definition change and on publish (audit trail)."""

    __tablename__ = "feature_version"
    __table_args__ = (UniqueConstraint("feature_id", "version_no", name="uq_feature_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("feature_def.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    change_note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    changed_by: Mapped[str] = mapped_column(String(160), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
