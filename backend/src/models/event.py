"""Account events — the upstream source of every feature value."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class EntityEvent(Base):
    __tablename__ = "entity_event"
    __table_args__ = (UniqueConstraint("entity_key", "event_type", "event_ts", name="uq_event_natural"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_key: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="app")
    source_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
