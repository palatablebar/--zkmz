"""Append-only event delivery ledger.

每行 = 上游一次事件投递（新增/更正/撤销）。``entity_event`` 是台账重放后的
规范化物化视图；回填以台账 seq 为水位重放「上次可用的事件状态」，而不是直接
读物化视图的当前值。台账只追加、不更新、不删除，撤销通过 ``action='retract'``
的新行表达。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class EventLedger(Base):
    __tablename__ = "event_ledger"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_event_ledger_delivery"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # 单调递增的投递序号，也是重放水位（backfill baseline_cutoff_seq 引用它）
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    delivery_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    entity_key: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # upsert = 新增/更正；retract = 撤销（amount 置 0）
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="upsert")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="app")
    source_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
