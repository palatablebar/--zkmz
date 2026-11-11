"""算法 A：点时间 join（point-in-time join）与泄漏检测。

口径（固定，前端只展示本模块结果）：

* 窗口：``strict`` = ``[label_time - W, label_time)``，``inclusive`` =
  ``(label_time - W, label_time]``（右端含标签时刻）。
* 聚合：``sum`` / ``count`` / ``max`` / ``last``，另有 ``recency_days``（= last
  的派生：距最近一条匹配事件的天数，无事件记 -1）。
* 泄漏口径：样本某特征在窗口内取到的事件里，若存在 ``event_ts >= label_time``
  即为泄漏（标签时刻之后的信息进入特征）。越界毫秒 = ``event_ts - label_time``：
  ``inclusive`` 边界吞掉「恰好等于标签时刻」的事件时越界为 0ms，记为
  ``boundary_equal``；若窗口右端被放宽（越界 > 0）记为 ``boundary_over``。
* 边界探针：合成 ``-1ms / 0ms / +1ms`` 三个事件，用同一 ``includes_event``
  判定，输出 strict / inclusive 的判定表（off-by-one 探针）。
* 失败态：时间戳无法归一 → ``bad_timestamp``；窗口内没有任何事件 →
  特征记 0（recency 记 -1）并在样本上标 ``no_event``（不 fail 整个 job）。

本模块是纯函数实现（不碰 DB），方便 seed、Celery 任务与 ``python -m``
自测共用同一份计算逻辑。
"""
from __future__ import annotations

import json
import sys
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from src.constants.enums import AggregateKind, BoundaryPolicy, FailureReason, LeakKind
from src.utils.timefmt import BadTimestamp, iso_ms_z, iso_z, parse_ts

WINDOW_SECONDS = {"1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


# --------------------------------------------------------------------------- #
# 数据对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FeatureSpec:
    """特征定义的计算视图（由 feature_def 行转换而来）。"""

    id: int
    code: str
    name: str
    window_seconds: int
    window_label: str
    boundary: str
    aggregate: str
    event_type: str | None = None
    amount_min: float | None = None
    description: str = ""


@dataclass(frozen=True)
class Event:
    id: int
    entity_key: str
    event_type: str
    ts: datetime
    amount: float


@dataclass(frozen=True)
class LabelRow:
    id: int
    label_set_id: int
    entity_key: str
    label_time: datetime
    label: int = 0


class PitFailure(Exception):
    """Job 级失败（bad_timestamp / no_feature / insufficient_samples）。"""

    def __init__(self, reason: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.detail = detail or {}


# --------------------------------------------------------------------------- #
# 归一化 / 载入
# --------------------------------------------------------------------------- #
def normalize_events(raw_events: Iterable[dict]) -> list[Event]:
    """把原始行（含字符串时间戳）归一化为 UTC Event 列表。

    时间戳无法解析时抛 ``PitFailure(bad_timestamp)``——这就是 job 的失败态之一。
    """
    events: list[Event] = []
    for index, raw in enumerate(raw_events):
        try:
            ts = parse_ts(raw.get("ts", raw.get("event_ts")))
        except BadTimestamp as exc:
            raise PitFailure(
                FailureReason.BAD_TIMESTAMP.value,
                f"事件时间戳无法解析：{exc}",
                {"row_index": index, "raw_ts": str(raw.get("ts", raw.get("event_ts")))},
            ) from exc
        events.append(
            Event(
                id=int(raw.get("id", index)),
                entity_key=str(raw["entity_key"]),
                event_type=str(raw.get("event_type", "")),
                ts=ts,
                amount=float(raw.get("amount") or 0),
            )
        )
    events.sort(key=lambda e: (e.entity_key, e.ts, e.id))
    return events


def normalize_label_rows(raw_rows: Iterable[dict]) -> list[LabelRow]:
    rows: list[LabelRow] = []
    for index, raw in enumerate(raw_rows):
        try:
            label_time = parse_ts(raw.get("label_time"))
        except BadTimestamp as exc:
            raise PitFailure(
                FailureReason.BAD_TIMESTAMP.value,
                f"标签时间戳无法解析：{exc}",
                {"row_index": index, "raw_label_time": str(raw.get("label_time"))},
            ) from exc
        rows.append(
            LabelRow(
                id=int(raw.get("id", index)),
                label_set_id=int(raw.get("label_set_id", 0)),
                entity_key=str(raw["entity_key"]),
                label_time=label_time,
                label=int(raw.get("label") or 0),
            )
        )
    rows.sort(key=lambda r: (r.label_time, r.entity_key, r.id))
    return rows


def parse_range(value, field: str) -> datetime:
    """解析 job / backfill 的范围参数；非法时间戳 → bad_timestamp 失败态。"""
    try:
        return parse_ts(value)
    except BadTimestamp as exc:
        raise PitFailure(
            FailureReason.BAD_TIMESTAMP.value,
            f"{field} 无法解析为时间戳",
            {"field": field, "raw": str(value)},
        ) from exc


def build_index(events: Sequence[Event]) -> dict[str, "EntityIndex"]:
    grouped: dict[str, list[Event]] = {}
    for event in events:
        grouped.setdefault(event.entity_key, []).append(event)
    return {key: EntityIndex(items) for key, items in grouped.items()}


class EntityIndex:
    """按 entity 分组并按时间有序，用二分定位窗口，避免全表扫。"""

    __slots__ = ("events", "timestamps")

    def __init__(self, events: list[Event]):
        self.events = events
        self.timestamps = [e.ts for e in events]

    def window(self, start: datetime, end: datetime, boundary: str) -> list[Event]:
        if boundary == BoundaryPolicy.INCLUSIVE.value:
            lo = bisect_right(self.timestamps, start)   # (start, ...
            hi = bisect_right(self.timestamps, end)     # ..., end]
        else:
            lo = bisect_left(self.timestamps, start)    # [start, ...
            hi = bisect_left(self.timestamps, end)      # ..., end)
        return self.events[lo:hi]


# --------------------------------------------------------------------------- #
# 窗口判定（探针复用同一函数，保证口径一致）
# --------------------------------------------------------------------------- #
def window_start(label_time: datetime, window_seconds: int) -> datetime:
    return label_time - timedelta(seconds=window_seconds)


def includes_event(ts: datetime, label_time: datetime, window_seconds: int, boundary: str) -> bool:
    start = window_start(label_time, window_seconds)
    if boundary == BoundaryPolicy.INCLUSIVE.value:
        return start < ts <= label_time
    return start <= ts < label_time


def aggregate(kind: str, events: Sequence[Event], label_time: datetime) -> float:
    if kind == AggregateKind.COUNT.value:
        return float(len(events))
    if not events:
        return -1.0 if kind == AggregateKind.RECENCY_DAYS.value else 0.0
    if kind == AggregateKind.SUM.value:
        return round(sum(e.amount for e in events), 2)
    if kind == AggregateKind.MAX.value:
        return round(max(e.amount for e in events), 2)
    latest = max(events, key=lambda e: (e.ts, e.id))
    if kind == AggregateKind.RECENCY_DAYS.value:
        delta = label_time - latest.ts
        return round(delta.total_seconds() / 86400.0, 3)
    return round(latest.amount, 2)


def _matches(spec: FeatureSpec, event: Event) -> bool:
    if spec.event_type and event.event_type != spec.event_type:
        return False
    if spec.amount_min is not None and event.amount < float(spec.amount_min):
        return False
    return True


def matched_events(spec: FeatureSpec, index: EntityIndex | None, label_time: datetime) -> list[Event]:
    if index is None:
        return []
    start = window_start(label_time, spec.window_seconds)
    candidates = index.window(start, label_time, spec.boundary)
    return [e for e in candidates if _matches(spec, e)]


# --------------------------------------------------------------------------- #
# 泄漏检测
# --------------------------------------------------------------------------- #
def detect_leak(spec: FeatureSpec, events: Sequence[Event], label_time: datetime) -> dict | None:
    """返回该「样本 × 特征」的泄漏详情；无泄漏返回 None。"""
    offending = [e for e in events if e.ts >= label_time]
    if not offending:
        return None
    worst = max(offending, key=lambda e: (e.ts, e.id))
    overflow_ms = int(round((worst.ts - label_time).total_seconds() * 1000))
    kind = LeakKind.BOUNDARY_EQUAL.value if overflow_ms == 0 else LeakKind.BOUNDARY_OVER.value
    return {
        "feature_code": spec.code,
        "feature_name": spec.name,
        "declared_boundary": spec.boundary,
        "effective_boundary": spec.boundary,
        "policy_mismatch": spec.boundary != BoundaryPolicy.STRICT.value,
        "kind": kind,
        "overflow_ms": overflow_ms,
        "event_id": worst.id,
        "event_type": worst.event_type,
        "event_ts": iso_ms_z(worst.ts),
        "label_time": iso_ms_z(label_time),
        "offending_events": len(offending),
    }


# --------------------------------------------------------------------------- #
# 边界探针（off-by-one 判定表）
# --------------------------------------------------------------------------- #
def boundary_probes(feature: FeatureSpec, label_time: datetime) -> list[dict]:
    """合成三个事件，验证 strict / inclusive 在右端的行为。"""
    offsets = [
        ("event_at_left_edge_minus_1ms", -1000, -1),
        ("event_at_label_time_minus_1ms", -1, -1),
        ("event_at_label_time", 0, 0),
        ("event_at_label_time_plus_1ms", 1, 1),
    ]
    probes: list[dict] = []
    for case, offset_us, offset_ms in offsets:
        ts = label_time + timedelta(microseconds=offset_us)
        in_strict = includes_event(ts, label_time, feature.window_seconds, BoundaryPolicy.STRICT.value)
        in_inclusive = includes_event(
            ts, label_time, feature.window_seconds, BoundaryPolicy.INCLUSIVE.value
        )
        probes.append(
            {
                "case": case,
                "offset_ms": offset_ms,
                "event_ts": iso_ms_z(ts),
                "included_strict": in_strict,
                "included_inclusive": in_inclusive,
                "verdict": (
                    "strict 排除、inclusive 纳入 → 越界 0ms"
                    if not in_strict and in_inclusive
                    else ("两种口径都不纳入" if not in_strict and not in_inclusive else "两种口径都纳入")
                ),
                "leak_under_inclusive": in_inclusive and not in_strict,
            }
        )
    return probes


# --------------------------------------------------------------------------- #
# 主流程：对一批标签行构建样本
# --------------------------------------------------------------------------- #
def build_samples(
    features: Sequence[FeatureSpec],
    events: Sequence[Event],
    label_rows: Sequence[LabelRow],
    effective_boundary: str | None = None,
) -> dict:
    """对每个标签行按每个特征做点时间 join，并检测泄漏。

    ``effective_boundary`` 为 job 参数快照里的边界策略：若给定，它会覆盖特征
    定义里的边界（这就是「inclusive 误用」的来源），泄漏检测仍按严格口径判断。
    """
    if not features:
        raise PitFailure(FailureReason.NO_FEATURE.value, "样本任务未选择任何特征")

    indexes = build_index(events)
    samples: list[dict] = []
    leaks: list[dict] = []
    no_event_samples = 0

    for row in label_rows:
        index = indexes.get(row.entity_key)
        features_json: dict[str, float] = {}
        feature_meta: dict[str, dict] = {}
        row_leaks: list[dict] = []
        any_event = False

        for spec in features:
            spec_eff = spec
            if effective_boundary and effective_boundary != spec.boundary:
                spec_eff = FeatureSpec(
                    id=spec.id,
                    code=spec.code,
                    name=spec.name,
                    window_seconds=spec.window_seconds,
                    window_label=spec.window_label,
                    boundary=effective_boundary,
                    aggregate=spec.aggregate,
                    event_type=spec.event_type,
                    amount_min=spec.amount_min,
                    description=spec.description,
                )
            selected = matched_events(spec_eff, index, row.label_time)
            features_json[spec.code] = aggregate(spec.aggregate, selected, row.label_time)
            feature_meta[spec.code] = {
                "matched_events": len(selected),
                "window_label": spec.window_label,
                "aggregate": spec.aggregate,
                "boundary": spec_eff.boundary,
                "declared_boundary": spec.boundary,
                "policy_mismatch": spec_eff.boundary != spec.boundary,
                "max_event_ts": iso_z(max((e.ts for e in selected), default=None)),
            }
            if selected:
                any_event = True
            leak = detect_leak(spec_eff, selected, row.label_time)
            if leak:
                leak.update(
                    {
                        "label_row_id": row.id,
                        "label_set_id": row.label_set_id,
                        "entity_key": row.entity_key,
                        "label": row.label,
                    }
                )
                row_leaks.append(leak)
                leaks.append(leak)

        if not any_event:
            no_event_samples += 1
        samples.append(
            {
                "label_row_id": row.id,
                "label_set_id": row.label_set_id,
                "entity_key": row.entity_key,
                "label_time": iso_z(row.label_time),
                "label": row.label,
                "features": features_json,
                "feature_meta": feature_meta,
                "leak_flags": row_leaks,
                "has_leak": bool(row_leaks),
                "no_event": not any_event,
            }
        )

    by_feature: dict[str, dict] = {}
    for leak in leaks:
        bucket = by_feature.setdefault(
            leak["feature_code"],
            {"feature_code": leak["feature_code"], "count": 0, "max_overflow_ms": 0, "policy": leak["declared_boundary"]},
        )
        bucket["count"] += 1
        bucket["max_overflow_ms"] = max(bucket["max_overflow_ms"], leak["overflow_ms"])

    return {
        "samples": samples,
        "leaks": leaks,
        "leak_summary": {
            "leak_count": len(leaks),
            "leak_samples": len({leak["label_row_id"] for leak in leaks}),
            "leak_features": len(by_feature),
            "by_feature": sorted(by_feature.values(), key=lambda b: -b["count"]),
            "max_overflow_ms": max((leak["overflow_ms"] for leak in leaks), default=0),
            "boundary_policies": sorted(
                {leak["declared_boundary"] for leak in leaks}
            ),
        },
        "sample_count": len(samples),
        "no_event_samples": no_event_samples,
    }


def build_report(
    features: Sequence[FeatureSpec],
    events: Sequence[Event],
    label_rows: Sequence[LabelRow],
    effective_boundary: str | None,
    matrix_limit: int = 24,
) -> dict:
    """构建落库用报告：泄漏明细 + 矩阵（泄漏优先截断）+ 边界探针。"""
    built = build_samples(features, events, label_rows, effective_boundary)
    samples = built["samples"]

    ordered = sorted(samples, key=lambda s: (not s["has_leak"], s["label_time"], s["entity_key"]))
    matrix_samples = ordered[:matrix_limit]
    matrix = {
        "features": [
            {"code": spec.code, "name": spec.name, "window_label": spec.window_label, "boundary": spec.boundary}
            for spec in features
        ],
        "samples": [
            {
                "label_row_id": s["label_row_id"],
                "entity_key": s["entity_key"],
                "label_time": s["label_time"],
                "label": s["label"],
                "cells": {
                    code: {
                        "value": s["features"][code],
                        "leak": any(
                            leak["feature_code"] == code for leak in s["leak_flags"]
                        ),
                        "overflow_ms": next(
                            (leak["overflow_ms"] for leak in s["leak_flags"] if leak["feature_code"] == code),
                            None,
                        ),
                        "matched_events": s["feature_meta"][code]["matched_events"],
                    }
                    for code in s["features"]
                },
            }
            for s in matrix_samples
        ],
        "total_samples": len(samples),
        "shown_samples": len(matrix_samples),
        "truncated": len(samples) > len(matrix_samples),
    }

    primary_feature = features[0]
    probe_label = label_rows[0].label_time if label_rows else datetime(2026, 1, 1, tzinfo=timezone.utc)
    probes = boundary_probes(primary_feature, probe_label)

    return {
        "_samples": samples,
        "leak_summary": built["leak_summary"],
        "leaks": built["leaks"],
        "matrix": matrix,
        "boundary_probes": probes,
        "sample_count": built["sample_count"],
        "no_event_samples": built["no_event_samples"],
        "leak_free": built["leak_summary"]["leak_count"] == 0,
    }


# --------------------------------------------------------------------------- #
# 自测（`python -m src.services.pit_engine`，同时也是 TESTING 的证据来源）
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    base = datetime(2026, 3, 12, 10, 30, 17, 420000, tzinfo=timezone.utc)
    spec = FeatureSpec(
        id=1,
        code="last_7d_amount",
        name="近 7 天最近一笔申请金额",
        window_seconds=WINDOW_SECONDS["7d"],
        window_label="7d",
        boundary="strict",
        aggregate="last",
        event_type="apply",
        amount_min=0.01,
    )
    raw = [
        {"id": 1, "entity_key": "ACC-1", "event_type": "apply", "ts": "2026-03-10T00:00:00Z", "amount": 100},
        {"id": 2, "entity_key": "ACC-1", "event_type": "apply", "ts": "2026-03-12T10:30:17.420Z", "amount": 250},
    ]
    events = normalize_events(raw)
    index = build_index(events)["ACC-1"]
    strict_hits = matched_events(spec, index, base)
    inclusive_spec = FeatureSpec(**{**spec.__dict__, "boundary": "inclusive"})
    inclusive_hits = matched_events(inclusive_spec, index, base)
    leak = detect_leak(inclusive_spec, inclusive_hits, base)
    probes = boundary_probes(spec, base)

    ok = (
        len(strict_hits) == 1
        and len(inclusive_hits) == 2
        and leak is not None
        and leak["overflow_ms"] == 0
        and probes[2]["leak_under_inclusive"] is True
    )
    try:
        normalize_events([{"entity_key": "ACC-1", "event_type": "apply", "ts": "2026-02-23 24:00:00"}])
        bad_ts_detected = False
    except PitFailure as exc:
        bad_ts_detected = exc.reason == FailureReason.BAD_TIMESTAMP.value
    ok = ok and bad_ts_detected

    print(
        json.dumps(
            {
                "self_test": "pit_engine",
                "strict_hits": len(strict_hits),
                "inclusive_hits": len(inclusive_hits),
                "leak_overflow_ms": leak["overflow_ms"] if leak else None,
                "boundary_equal_probe": probes[2],
                "bad_timestamp_detected": bad_ts_detected,
                "ok": ok,
            },
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_self_test())
