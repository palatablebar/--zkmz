"""Feature backfill task + full/incremental consistency result."""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class BackfillTask(Base):
    __tablename__ = "backfill_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 旧字段：范围中点水位（已废弃——按事件时间中点切分会裁掉窗口历史）。
    # 保留仅供历史报告展示，新逻辑以 baseline_cutoff_seq 为准。
    base_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 上次成功运行固定下来的台账水位（event_ledger.seq）；None = 首次运行，无基准。
    baseline_cutoff_seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    baseline_event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feature_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    full_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    incremental_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invariant_hold: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="system")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
