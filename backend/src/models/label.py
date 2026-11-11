"""Label set + its label rows (one row = one training sample key)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class LabelSet(Base):
    __tablename__ = "label_set"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LabelRow(Base):
    __tablename__ = "label_row"
    __table_args__ = (UniqueConstraint("label_set_id", "entity_key", "label_time", name="uq_label_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_set_id: Mapped[int] = mapped_column(ForeignKey("label_set.id"), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    label_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raw_label_time: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    label: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
