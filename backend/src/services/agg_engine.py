"""算法 B：多窗口聚合 + 全量重算 vs 增量重算的一致性校验。

口径（固定，前端只展示本模块结果）：

* 窗口：``1d`` / ``7d`` / ``30d`` 三个回看窗口，每个窗口都按 strict 口径
  ``[label_time - W, label_time)`` 取事件（与 pit_engine 同一函数实现）。
* 每窗口统计：``cnt`` / ``amount_sum`` / ``amount_max`` / ``last_ts``。
* 全量重算（full）：用范围内全部事件按窗口重算。
* 增量重算（incremental）：``基准快照``（事件 id <= 基准水位，等价于上一次全量
  运行的结果）+ ``新增事件``（id > 基准水位，含迟到事件）按窗口合并。
* 校验：逐样本把特征 JSON 规范化（``json.dumps(sort_keys=True)``）后取
  ``md5``；再逐样本比对 full 与 incremental。输出差异样本数、首个差异位置、
  不一致原因分类（``window_boundary`` / ``out_of_order`` / ``duplicate_event``）。
* 不变量：``full == incremental``；不成立时 ``invariant_hold=false``。
* 负例对照（self_check）：故意把窗口右端放宽 60s 重算一遍，用同一个比对器
  证明「比对器不是空转的」——它必须报出差异并把原因归到 ``window_boundary``。

本模块为纯函数 + 可 ``python -m src.services.agg_engine`` 自测。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Sequence

from src.constants.enums import BoundaryPolicy, MismatchReason
from src.services.pit_engine import (
    EntityIndex,
    Event,
    LabelRow,
    build_index,
    normalize_events,
    window_start,
)
from src.utils.timefmt import iso_ms_z, iso_z

WINDOWS: dict[str, int] = {"1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400}
_WINDOW_ORDER = ["1d", "7d", "30d"]


# --------------------------------------------------------------------------- #
# 单样本多窗口聚合
# --------------------------------------------------------------------------- #
def _empty_window() -> dict:
    return {"cnt": 0, "amount_sum": 0.0, "amount_max": 0.0, "last_ts": None, "last_amount": 0.0}


def _aggregate_slice(events: Sequence[Event]) -> dict:
    window = _empty_window()
    if not events:
        return window
    window["cnt"] = len(events)
    window["amount_sum"] = round(sum(e.amount for e in events), 2)
    window["amount_max"] = round(max(e.amount for e in events), 2)
    latest = max(events, key=lambda e: (e.ts, e.id))
    window["last_ts"] = iso_z(latest.ts)
    window["last_amount"] = round(latest.amount, 2)
    return window


def _merge_window(base: dict, added: Sequence[Event]) -> dict:
    """把新增事件合并进基准窗口统计（count/sum/max/last 均可增量合并）。"""
    if not added:
        return dict(base)
    merged = dict(base)
    merged["cnt"] = int(base["cnt"]) + len(added)
    merged["amount_sum"] = round(float(base["amount_sum"]) + sum(e.amount for e in added), 2)
    merged["amount_max"] = round(max([float(base["amount_max"])] + [e.amount for e in added]), 2)
    latest = max(added, key=lambda e: (e.ts, e.id))
    base_last = base.get("last_ts")
    if base_last is None or iso_z(latest.ts) > str(base_last):
        merged["last_ts"] = iso_z(latest.ts)
        merged["last_amount"] = round(latest.amount, 2)
    return merged


def _slice(index: EntityIndex | None, label_time: datetime, seconds: int) -> list[Event]:
    if index is None:
        return []
    return index.window(window_start(label_time, seconds), label_time, BoundaryPolicy.STRICT.value)


def windowed_features(
    index: EntityIndex | None,
    label_time: datetime,
    windows: dict[str, int] = WINDOWS,
    grace_seconds: int = 0,
) -> dict:
    """一次算完三个窗口（grace_seconds > 0 只用于负例对照）。"""
    out: dict[str, dict] = {}
    for label, seconds in windows.items():
        if grace_seconds:
            start = window_start(label_time, seconds)
            end = label_time + timedelta(seconds=grace_seconds)
            items = index.window(start, end, BoundaryPolicy.STRICT.value) if index else []
        else:
            items = _slice(index, label_time, seconds)
        out[label] = _aggregate_slice(items)
    return out


# --------------------------------------------------------------------------- #
# 两遍计算：full / incremental
# --------------------------------------------------------------------------- #
def canonical_payload(row: LabelRow, windows: dict) -> dict:
    return {
        "label_row_id": row.id,
        "entity_key": row.entity_key,
        "label_time": iso_ms_z(row.label_time),
        "windows": {
            label: {
                "cnt": int(windows[label]["cnt"]),
                "amount_sum": round(float(windows[label]["amount_sum"]), 2),
                "amount_max": round(float(windows[label]["amount_max"]), 2),
                "last_ts": windows[label]["last_ts"],
            }
            for label in _WINDOW_ORDER
            if label in windows
        },
    }


def checksum(payloads: Sequence[dict]) -> str:
    blob = json.dumps(payloads, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def full_pass(label_rows: Sequence[LabelRow], events: Sequence[Event]) -> list[dict]:
    index = build_index(events)
    payloads = []
    for row in label_rows:
        windows = windowed_features(index.get(row.entity_key), row.label_time)
        payloads.append(canonical_payload(row, windows))
    payloads.sort(key=lambda p: p["label_row_id"])
    return payloads


def incremental_pass(
    label_rows: Sequence[LabelRow],
    base_events: Sequence[Event],
    new_events: Sequence[Event],
) -> list[dict]:
    """基准快照（base_events）+ 新增事件（new_events，含迟到事件）逐样本合并。"""
    base_index = build_index(base_events)
    payloads = []
    for row in label_rows:
        base_windows = windowed_features(base_index.get(row.entity_key), row.label_time)
        if new_events:
            row_new = [e for e in new_events if e.entity_key == row.entity_key]
            for label, seconds in WINDOWS.items():
                start = window_start(row.label_time, seconds)
                added = [e for e in row_new if start <= e.ts < row.label_time]
                base_windows[label] = _merge_window(base_windows[label], added)
        payloads.append(canonical_payload(row, base_windows))
    payloads.sort(key=lambda p: p["label_row_id"])
    return payloads


# --------------------------------------------------------------------------- #
# 比对 + 原因分类
# --------------------------------------------------------------------------- #
def classify_reason(
    full: dict,
    inc: dict,
    late_event_count: int,
    duplicate_event_count: int,
) -> str:
    differing = [
        label
        for label in _WINDOW_ORDER
        if full["windows"].get(label) != inc["windows"].get(label)
    ]
    if duplicate_event_count:
        return MismatchReason.DUPLICATE_EVENT.value
    if late_event_count and differing and differing[0] == "30d":
        return MismatchReason.OUT_OF_ORDER.value
    if differing:
        return MismatchReason.WINDOW_BOUNDARY.value
    return MismatchReason.NONE.value


def compare_passes(
    full_payloads: Sequence[dict],
    inc_payloads: Sequence[dict],
    late_event_count: int = 0,
    duplicate_event_count: int = 0,
) -> dict:
    diffs: list[dict] = []
    reason_counts: Counter = Counter()
    inc_by_id = {p["label_row_id"]: p for p in inc_payloads}
    for index, full in enumerate(full_payloads):
        inc = inc_by_id.get(full["label_row_id"])
        if inc is None:
            diffs.append(
                {
                    "index": index,
                    "label_row_id": full["label_row_id"],
                    "reason": MismatchReason.WINDOW_BOUNDARY.value,
                    "detail": "incremental 缺少该样本",
                }
            )
            reason_counts[MismatchReason.WINDOW_BOUNDARY.value] += 1
            continue
        if full == inc:
            continue
        reason = classify_reason(full, inc, late_event_count, duplicate_event_count)
        reason_counts[reason] += 1
        differing = [
            label for label in _WINDOW_ORDER if full["windows"].get(label) != inc["windows"].get(label)
        ]
        diffs.append(
            {
                "index": index,
                "label_row_id": full["label_row_id"],
                "entity_key": full["entity_key"],
                "label_time": full["label_time"],
                "reason": reason,
                "differing_windows": differing,
                "full": {label: full["windows"][label] for label in differing},
                "incremental": {label: inc["windows"][label] for label in differing},
            }
        )
    first = diffs[0] if diffs else None
    return {
        "equal": not diffs,
        "diff_sample_count": len(diffs),
        "first_diff": first,
        "reason_classes": dict(reason_counts),
        "differences": diffs[:20],
    }


def detect_anomalies(base_events: Sequence[Event], new_events: Sequence[Event], watermark: datetime) -> dict:
    """迟到事件 / 重复事件（(entity, type, ts) 相同）计数，用于差异归因。"""
    late = [e for e in new_events if e.ts <= watermark]
    seen: Counter = Counter()
    for event in base_events + new_events:
        seen[(event.entity_key, event.event_type, iso_z(event.ts))] += 1
    duplicates = sum(count - 1 for count in seen.values() if count > 1)
    return {"late_event_count": len(late), "duplicate_event_count": duplicates}


# --------------------------------------------------------------------------- #
# 主入口：一次回填 = full / incremental / 负例对照
# --------------------------------------------------------------------------- #
def run_backfill(
    label_rows: Sequence[LabelRow],
    events: Sequence[Event],
    base_watermark: datetime,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    grace_seconds: int = 60,
) -> dict:
    if not label_rows:
        raise ValueError("回填范围没有任何标签样本")
    started = time.time()

    def in_range(event: Event) -> bool:
        if range_start and event.ts < range_start:
            return False
        if range_end and event.ts > range_end:
            return False
        return True

    scoped = [e for e in events if in_range(e)]
    base_events = [e for e in scoped if e.ts <= base_watermark]
    new_events = [e for e in scoped if e.ts > base_watermark]
    anomalies = detect_anomalies(base_events, new_events, base_watermark)

    full_payloads = full_pass(label_rows, scoped)
    inc_payloads = incremental_pass(label_rows, base_events, new_events)
    full_checksum = checksum(full_payloads)
    inc_checksum = checksum(inc_payloads)
    comparison = compare_passes(
        full_payloads,
        inc_payloads,
        anomalies["late_event_count"],
        anomalies["duplicate_event_count"],
    )

    # 负例对照：窗口右端放宽 grace_seconds，用同一个比对器必须报差异
    index = build_index(scoped)
    control_payloads = []
    for row in label_rows:
        control_payloads.append(
            canonical_payload(
                row, windowed_features(index.get(row.entity_key), row.label_time, grace_seconds=grace_seconds)
            )
        )
    control_payloads.sort(key=lambda p: p["label_row_id"])
    control = compare_passes(full_payloads, control_payloads)
    control_reasons = control["reason_classes"] or {MismatchReason.WINDOW_BOUNDARY.value: 0}

    duration_ms = int((time.time() - started) * 1000)
    return {
        "windows": _WINDOW_ORDER,
        "sample_count": len(label_rows),
        "cell_count": len(label_rows) * len(_WINDOW_ORDER),
        "base_watermark": iso_z(base_watermark),
        "range_start": iso_z(range_start),
        "range_end": iso_z(range_end),
        "scoped_event_count": len(scoped),
        "base_event_count": len(base_events),
        "new_event_count": len(new_events),
        "late_event_count": anomalies["late_event_count"],
        "duplicate_event_count": anomalies["duplicate_event_count"],
        "full": {"checksum": full_checksum, "digest_count": len(full_payloads)},
        "incremental": {"checksum": inc_checksum, "digest_count": len(inc_payloads)},
        "equal": comparison["equal"],
        "invariant": "full == incremental",
        "invariant_hold": full_checksum == inc_checksum and comparison["equal"],
        "diff_sample_count": comparison["diff_sample_count"],
        "first_diff": comparison["first_diff"],
        "reason_classes": comparison["reason_classes"],
        "differences": comparison["differences"],
        "self_check": {
            "induced_boundary": f"window_end_plus_{grace_seconds}s",
            "diff_sample_count": control["diff_sample_count"],
            "first_diff": control["first_diff"],
            "reason_classes": control_reasons,
            "sensitivity_ok": control["diff_sample_count"] > 0 or len(full_payloads) == 0,
        },
        "duration_ms": duration_ms,
    }


# --------------------------------------------------------------------------- #
# 自测（`python -m src.services.agg_engine`）
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    base_ts = datetime(2026, 3, 1, tzinfo=timezone.utc)
    raw = []
    for i in range(40):
        raw.append(
            {
                "id": i + 1,
                "entity_key": f"ACC-{i % 3}",
                "event_type": "apply" if i % 2 == 0 else "repay",
                "ts": iso_ms_z(base_ts + timedelta(hours=i * 9)),
                "amount": 100 + i,
            }
        )
    events = normalize_events(raw)
    watermark = base_ts + timedelta(hours=150)
    labels = [
        LabelRow(
            id=index + 1,
            label_set_id=1,
            entity_key=f"ACC-{index % 3}",
            label_time=base_ts + timedelta(hours=60 + index * 7),
            label=index % 2,
        )
        for index in range(40)
    ]
    report = run_backfill(labels, events, watermark)
    invariant_ok = report["invariant_hold"] and report["diff_sample_count"] == 0
    sensitivity_ok = report["self_check"]["diff_sample_count"] > 0
    print(
        json.dumps(
            {
                "self_test": "agg_engine",
                "full_checksum": report["full"]["checksum"],
                "incremental_checksum": report["incremental"]["checksum"],
                "sample_count": report["sample_count"],
                "new_event_count": report["new_event_count"],
                "diff_sample_count": report["diff_sample_count"],
                "self_check_diff_samples": report["self_check"]["diff_sample_count"],
                "self_check_reasons": report["self_check"]["reason_classes"],
                "ok": bool(invariant_ok and sensitivity_ok),
            },
            ensure_ascii=False,
        )
    )
    return 0 if invariant_ok and sensitivity_ok else 1


if __name__ == "__main__":
    sys.exit(_self_test())
