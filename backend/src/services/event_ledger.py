"""事件投递台账（append-only ledger）与规范化事件状态重放。

上游事件以「投递批次」方式到达，同一条业务事件（自然键
``(entity_key, event_type, event_ts)``）可能被重复投递、更正（金额/渠道修正）
或撤销。直接读 ``entity_event`` 当前值无法回答「上一次回填看到的事件状态是什么、
这之后到了哪些新增与更正」，因此所有投递先落 **append-only 台账**，再由本模块
按 ``seq`` 顺序重放出某个水位下的规范化状态。

台账动作（``action``）：

* ``upsert``  —— 新增或更正一条业务事件；同一 ``delivery_id`` 重复投递 **只生效一次**；
* ``retract`` —— 撤销一条业务事件（自然键必须能在当前状态中找到，否则批次未对平）。

规范化规则（纯函数，不碰 DB，供 backfill / seed / 自测共用）：

1. 严格按 ``seq`` 升序处理，``seq`` 即「上次可用状态」的水位；
2. ``delivery_id`` 去重：已生效过的投递再次出现记为 ``duplicate_delivery``，忽略；
3. ``upsert`` 命中已存在自然键记为 ``replaced``（更正），否则记为 ``accepted``（新增）；
4. ``retract`` 命中记为 ``retracted``；找不到自然键记为 ``retract_missing``（未对平）；
5. 重放结果是 ``自然键 -> Event`` 的不可变快照，作为回填的「基准事件状态」。

未对平（``aligned=False``）的三种情况：重复 ``delivery_id``、撤销缺失、更正/撤销了
基准水位内已经生效的事件（基准被改写，旧结果不可增量复用）。未对平时由调用方保留
上一次结果，本模块只负责给出结构化判定，不抛异常、不吞信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

from src.services.pit_engine import Event
from src.utils.timefmt import iso_z

UPSERT = "upsert"
RETRACT = "retract"

ACCEPTED = "accepted"
REPLACED = "replaced"
RETRACTED = "retracted"
IGNORED_DUPLICATE = "duplicate_delivery"
RETRACT_MISSING = "retract_missing"


@dataclass(frozen=True)
class LedgerEntry:
    """一次事件投递（对应 ``event_ledger`` 一行）。"""

    seq: int
    delivery_id: str
    entity_key: str
    event_type: str
    event_ts: datetime
    action: str = UPSERT
    amount: float = 0.0
    channel: str = "app"
    source_ref: str = ""
    batch_id: str = ""


@dataclass
class ReplayState:
    """重放到某个水位后的规范化事件状态 + 逐条投递的处置台账。"""

    events: dict[tuple, Event] = field(default_factory=dict)
    dispositions: list[dict] = field(default_factory=list)
    seen_delivery_ids: set[str] = field(default_factory=set)

    def as_events(self) -> list[Event]:
        """与 ``normalize_events`` 同序：(entity, ts, id) 有序，供 build_index 使用。"""
        return sorted(self.events.values(), key=lambda e: (e.entity_key, e.ts, e.id))


def natural_key(entity_key: str, event_type: str, event_ts: datetime) -> tuple[str, str, str]:
    return entity_key, event_type, iso_z(event_ts)


def _disposition(entry: LedgerEntry, outcome: str, before: Event | None, after: Event | None) -> dict:
    return {
        "seq": entry.seq,
        "batch_id": entry.batch_id,
        "delivery_id": entry.delivery_id,
        "action": entry.action,
        "outcome": outcome,
        "entity_key": entry.entity_key,
        "event_type": entry.event_type,
        "event_ts": iso_z(entry.event_ts),
        "amount_before": round(before.amount, 2) if before is not None else None,
        "amount_after": round(after.amount, 2) if after is not None else None,
        "canonical_event_id": after.id if after is not None else (before.id if before is not None else None),
    }


def replay(
    entries: Iterable[LedgerEntry],
    cutoff_seq: int | None = None,
    state: ReplayState | None = None,
) -> ReplayState:
    """按 seq 顺序重放台账。

    ``cutoff_seq`` 给定时只处理 ``seq <= cutoff_seq`` 的投递（固定「上次可用状态」）；
    ``state`` 可传入更早水位的状态做增量重放（调用方通常直接全量重放，逻辑等价且
    更易审计）。返回的 ``dispositions`` 与输入条目同序，记录每条投递的处置结果。
    """
    current = state or ReplayState()
    ordered = sorted(entries, key=lambda item: item.seq)
    for entry in ordered:
        if cutoff_seq is not None and entry.seq > cutoff_seq:
            break
        if entry.delivery_id in current.seen_delivery_ids:
            current.dispositions.append(_disposition(entry, IGNORED_DUPLICATE, None, None))
            continue
        current.seen_delivery_ids.add(entry.delivery_id)
        key = natural_key(entry.entity_key, entry.event_type, entry.event_ts)
        before = current.events.get(key)
        if entry.action == RETRACT:
            if before is None:
                current.dispositions.append(_disposition(entry, RETRACT_MISSING, None, None))
                continue
            del current.events[key]
            current.dispositions.append(_disposition(entry, RETRACTED, before, None))
            continue
        after = Event(
            id=entry.seq,
            entity_key=entry.entity_key,
            event_type=entry.event_type,
            ts=entry.event_ts,
            amount=float(entry.amount or 0.0),
        )
        outcome = REPLACED if before is not None else ACCEPTED
        current.events[key] = after
        current.dispositions.append(_disposition(entry, outcome, before, after))
    return current


def replay_snapshot(entries: Sequence[LedgerEntry], cutoff_seq: int | None) -> list[Event]:
    """便捷封装：重放至 ``cutoff_seq``，返回规范化事件列表。"""
    return replay(entries, cutoff_seq=cutoff_seq).as_events()


def classify_batch(
    new_entries: Sequence[LedgerEntry],
    dispositions: Sequence[dict],
    baseline_keys: set[tuple],
) -> dict:
    """判定本批次（``new_entries``，即 seq 大于基准水位的投递）是否与基准对平。

    未对平条件（任一即不可增量复用旧结果）：

    * ``duplicate_delivery`` —— 同一 delivery_id 重复投递（信息已被忽略，需上游确认）；
    * ``retract_missing``    —— 撤销了一个当前状态里不存在的自然键；
    * ``baseline_rewritten`` —— 更正/撤销命中了基准快照里已存在的自然键，基准被改写。
      同批次内「先新增、后更正」的自然键不在基准里，不算改写。
    """
    disposition_by_seq = {item["seq"]: item for item in dispositions}
    issues: list[dict] = []
    for entry in new_entries:
        item = disposition_by_seq.get(entry.seq)
        if item is None:
            continue
        outcome = item["outcome"]
        key = natural_key(entry.entity_key, entry.event_type, entry.event_ts)
        if outcome == IGNORED_DUPLICATE:
            issues.append({"seq": entry.seq, "reason": IGNORED_DUPLICATE, "detail": item})
        elif outcome == RETRACT_MISSING:
            issues.append({"seq": entry.seq, "reason": RETRACT_MISSING, "detail": item})
        elif outcome in (REPLACED, RETRACTED) and key in baseline_keys:
            issues.append(
                {
                    "seq": entry.seq,
                    "reason": "baseline_rewritten",
                    "detail": {
                        "outcome": outcome,
                        "entity_key": entry.entity_key,
                        "event_type": entry.event_type,
                        "event_ts": item["event_ts"],
                        "amount_before": item["amount_before"],
                        "amount_after": item["amount_after"],
                    },
                }
            )
    return {
        "aligned": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }
