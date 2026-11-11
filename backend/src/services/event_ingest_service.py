"""事件投递接入：写 append-only 台账并重放物化 ``entity_event``。

所有上游事件（含 seed）都走 :func:`ingest_deliveries` 这一条通道：

1. 取当前最大 ``seq``，新投递按输入顺序追加 ``event_ledger``（``delivery_id``
   唯一约束兜底，重复投递在落库层就无法二次生效）；
2. 重放全量台账得到规范化事件状态，UPSERT 同步到物化视图 ``entity_event``
   （自然键 ``(entity_key, event_type, event_ts)`` 唯一）；被撤销的事件从物化
   视图删除，但台账行永久保留；
3. 返回本批次的台账条目与处置结果，供调用方（seed / 回填对账 / API）复用。

本模块是唯一允许写 ``entity_event`` / ``event_ledger`` 的地方。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import EntityEvent, EventLedger
from src.services import event_ledger
from src.services.event_ledger import LedgerEntry
from src.services.pit_engine import Event
from src.utils.timefmt import iso_z, utcnow


def _max_seq(db: Session) -> int:
    return int(db.scalar(select(EventLedger.seq).order_by(EventLedger.seq.desc()).limit(1)) or 0)


def load_ledger(db: Session, cutoff_seq: int | None = None) -> list[LedgerEntry]:
    """读取台账（可限定水位），转换为引擎用的 LedgerEntry。"""
    stmt = select(EventLedger).order_by(EventLedger.seq)
    if cutoff_seq is not None:
        stmt = stmt.where(EventLedger.seq <= cutoff_seq)
    rows = list(db.scalars(stmt))
    return [
        LedgerEntry(
            seq=row.seq,
            delivery_id=row.delivery_id,
            entity_key=row.entity_key,
            event_type=row.event_type,
            event_ts=row.event_ts,
            action=row.action,
            amount=float(row.amount),
            channel=row.channel,
            source_ref=row.source_ref,
            batch_id=row.batch_id,
        )
        for row in rows
    ]


def ingest_deliveries(
    db: Session,
    deliveries: list[dict],
    batch_id: str,
    is_seed: bool = False,
) -> dict:
    """追加一批投递并刷新物化视图。

    每个 delivery 字典字段：``delivery_id`` / ``entity_key`` / ``event_type`` /
    ``event_ts`` / ``amount`` / ``action``(默认 upsert) / ``channel`` /
    ``source_ref``。已存在的 ``delivery_id`` 跳过（幂等，重复投递只生效一次）。
    """
    if not deliveries:
        return {"batch_id": batch_id, "appended": 0, "skipped_duplicates": 0, "entries": []}

    existing_ids = set(db.scalars(select(EventLedger.delivery_id)))
    next_seq = _max_seq(db) + 1
    appended: list[EventLedger] = []
    skipped = 0
    for item in deliveries:
        delivery_id = str(item["delivery_id"])
        if delivery_id in existing_ids:
            skipped += 1
            continue
        existing_ids.add(delivery_id)
        entry = EventLedger(
            seq=next_seq,
            delivery_id=delivery_id,
            batch_id=batch_id,
            entity_key=item["entity_key"],
            event_type=item["event_type"],
            event_ts=item["event_ts"],
            action=item.get("action", event_ledger.UPSERT),
            amount=item.get("amount", 0) or 0,
            channel=item.get("channel", "app"),
            source_ref=item.get("source_ref", ""),
            is_seed=is_seed,
        )
        db.add(entry)
        appended.append(entry)
        next_seq += 1
    db.flush()

    if appended:
        _refresh_materialized_view(db)
    return {
        "batch_id": batch_id,
        "appended": len(appended),
        "skipped_duplicates": skipped,
        "entries": [
            LedgerEntry(
                seq=row.seq,
                delivery_id=row.delivery_id,
                entity_key=row.entity_key,
                event_type=row.event_type,
                event_ts=row.event_ts,
                action=row.action,
                amount=float(row.amount),
                channel=row.channel,
                source_ref=row.source_ref,
                batch_id=row.batch_id,
            )
            for row in appended
        ],
    }


def _refresh_materialized_view(db: Session) -> None:
    """全量重放台账 → UPSERT 同步 entity_event，删除被撤销的自然键。"""
    ledger_rows = list(db.scalars(select(EventLedger).order_by(EventLedger.seq)))
    entries = [
        LedgerEntry(
            seq=row.seq,
            delivery_id=row.delivery_id,
            entity_key=row.entity_key,
            event_type=row.event_type,
            event_ts=row.event_ts,
            action=row.action,
            amount=float(row.amount),
            channel=row.channel,
            source_ref=row.source_ref,
            batch_id=row.batch_id,
        )
        for row in ledger_rows
    ]
    entry_by_seq = {row.seq: row for row in ledger_rows}
    state = event_ledger.replay(entries)
    canonical = state.as_events()
    wanted_keys = {
        (event.entity_key, event.event_type, iso_z(event.ts)): event for event in canonical
    }

    current = list(db.scalars(select(EntityEvent)))
    current_by_key = {
        (row.entity_key, row.event_type, iso_z(row.event_ts)): row for row in current
    }
    for key, row in current_by_key.items():
        if key not in wanted_keys:
            db.delete(row)

    for key, event in wanted_keys.items():
        row = current_by_key.get(key)
        if row is None:
            source = _source_for(entry_by_seq, event)
            db.add(
                EntityEvent(
                    entity_key=event.entity_key,
                    event_type=event.event_type,
                    event_ts=event.ts,
                    amount=event.amount,
                    channel=source["channel"],
                    source_ref=source["source_ref"],
                    is_seed=source["is_seed"],
                )
            )
        elif float(row.amount) != event.amount:
            row.amount = event.amount
    db.flush()


def _source_for(entry_by_seq: dict[int, EventLedger], event: Event) -> dict:
    """规范化事件的 id 即最后一次 upsert 的台账 seq，直接取回渠道/来源标记。"""
    entry = entry_by_seq.get(event.id)
    if entry is None:
        return {"channel": "app", "source_ref": "", "is_seed": False}
    return {"channel": entry.channel, "source_ref": entry.source_ref, "is_seed": entry.is_seed}


def next_batch_id(prefix: str = "BATCH") -> str:
    return f"{prefix}-{utcnow().strftime('%Y%m%d%H%M%S')}"
