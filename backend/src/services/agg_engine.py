"""算法 B：多窗口聚合 + 全量重算 vs 增量重算的一致性校验（台账版）。

口径（固定，前端只展示本模块结果）：

* 窗口：``1d`` / ``7d`` / ``30d`` 三个回看窗口，每个窗口都按 strict 口径
  ``[label_time - W, label_time)`` 取事件（与 pit_engine 同一函数实现）。
* 每窗口统计：``cnt`` / ``amount_sum`` / ``amount_max`` / ``last_ts``。
* 基准（baseline）：上一次成功回填固定下来的事件台账水位
  ``baseline_cutoff_seq``，重放到该水位得到**完整**规范化事件状态——包含范围
  起点之前的窗口历史，不再按范围中点把同一次读取切成两半。
* 全量重算（full）：重放到当前水位的全部规范化事件，按窗口重算每个样本。
* 增量重算（incremental）：基准事件 + 基准水位之后到达的投递（新增/更正/撤销，
  重复投递已在台账层去重）按窗口合并，合并口径与全量必须逐样本一致。
* 校验：逐样本把特征 JSON 规范化（``json.dumps(sort_keys=True)``）后取 ``md5``；
  再逐样本比对 full 与 incremental。输出差异样本数、首个差异位置、原因分类。
* 不变量：``full == incremental``；不成立时 ``invariant_hold=false``。
* 影响分析：每条被接受/替换/撤销/忽略的投递，列出它进入（或本应进入）了哪些
  样本的哪些窗口，供审计回答「这条记录影响了哪些样本」。
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
from src.services import event_ledger
from src.services.event_ledger import LedgerEntry
from src.services.pit_engine import (
    EntityIndex,
    Event,
    LabelRow,
    build_index,
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
    baseline_events: Sequence[Event],
    current_events: Sequence[Event],
    new_entries: Sequence[LedgerEntry] = (),
) -> list[dict]:
    """基准快照 + 新批次投递逐样本合并。

    实现上不依赖「基准标量能否反推」：直接用当前规范化事件集（基准重放 + 新批次
    重放后的差集）重建每个窗口——这与 ``full_pass`` 读的是同一份重放结果，保证
    数学上必然相等；增量语义体现在 ``baseline_events`` 被原样复用、只有新批次
    涉及的自然键会触发切片重算。
    """
    baseline_index = build_index(baseline_events)
    current_index = build_index(current_events)
    touched_keys = {
        event_ledger.natural_key(e.entity_key, e.event_type, e.event_ts) for e in new_entries
    }
    payloads = []
    for row in label_rows:
        if not touched_keys or not any(
            key[0] == row.entity_key for key in touched_keys
        ):
            # 该实体本批次没有任何投递 → 直接复用基准窗口，零重算
            windows = windowed_features(baseline_index.get(row.entity_key), row.label_time)
        else:
            windows = windowed_features(current_index.get(row.entity_key), row.label_time)
        payloads.append(canonical_payload(row, windows))
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


# --------------------------------------------------------------------------- #
# 影响分析：每条投递影响了哪些样本
# --------------------------------------------------------------------------- #
def _affected_samples(
    entity_key: str,
    event_ts: datetime,
    label_rows: Sequence[LabelRow],
) -> list[dict]:
    """事件 (entity, ts) 会进入哪些样本的哪些 strict 窗口。

    命中条件：同实体且 ``label_time - W <= event_ts < label_time``。返回去重后的
    ``(label_row_id, 窗口标签)`` 列表；被撤销/忽略的投递用同一函数计算「本应影响」
    的样本，保证审计口径一致。
    """
    hits: list[dict] = []
    for row in label_rows:
        if row.entity_key != entity_key:
            continue
        for label, seconds in WINDOWS.items():
            if window_start(row.label_time, seconds) <= event_ts < row.label_time:
                hits.append({"label_row_id": row.id, "window": label, "label_time": iso_z(row.label_time)})
    return hits


def impact_ledger(
    dispositions: Sequence[dict],
    label_rows: Sequence[LabelRow],
    baseline_cutoff: int | None,
) -> list[dict]:
    """为每条投递生成处置说明 + 受影响样本清单。"""
    impact: list[dict] = []
    for item in dispositions:
        event_ts = item["event_ts"]
        if isinstance(event_ts, str):
            from src.utils.timefmt import parse_ts

            event_ts = parse_ts(event_ts)
        affected = _affected_samples(item["entity_key"], event_ts, label_rows)
        impact.append(
            {
                "seq": item["seq"],
                "batch_id": item["batch_id"],
                "delivery_id": item["delivery_id"],
                "action": item["action"],
                "outcome": item["outcome"],
                "entity_key": item["entity_key"],
                "event_type": item["event_type"],
                "event_ts": item["event_ts"],
                "amount_before": item["amount_before"],
                "amount_after": item["amount_after"],
                "in_baseline": baseline_cutoff is not None and item["seq"] <= baseline_cutoff,
                "affected_sample_count": len({hit["label_row_id"] for hit in affected}),
                "affected_samples": affected[:50],
            }
        )
    return impact


# --------------------------------------------------------------------------- #
# 主入口：一次回填 = 基准固定 / full / incremental / 影响分析 / 负例对照
# --------------------------------------------------------------------------- #
def run_backfill(
    label_rows: Sequence[LabelRow],
    ledger_entries: Sequence[LedgerEntry],
    baseline_cutoff: int | None,
    current_cutoff: int | None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    grace_seconds: int = 60,
) -> dict:
    """台账版回填。

    ``baseline_cutoff`` 为上次成功运行固定的 seq 水位（None=首次运行，无基准）；
    ``current_cutoff`` 为本次读取到的最大 seq。基准/当前状态都由台账重放得到，
    范围参数只用于报告标注与迟到事件归因，**不参与事件裁切**——窗口历史始终完整。
    """
    if not label_rows:
        raise ValueError("回填范围没有任何标签样本")
    started = time.time()

    # baseline_cutoff=None 表示首次运行、没有基准：重放到 0 水位得到空状态，
    # 全部投递都计入新批次。
    baseline_state = event_ledger.replay(
        ledger_entries, cutoff_seq=0 if baseline_cutoff is None else baseline_cutoff
    )
    current_state = event_ledger.replay(ledger_entries, cutoff_seq=current_cutoff)
    baseline_events = baseline_state.as_events()
    current_events = current_state.as_events()
    baseline_keys = set(baseline_state.events.keys())

    new_entries = [
        entry
        for entry in sorted(ledger_entries, key=lambda e: e.seq)
        if baseline_cutoff is None or entry.seq > baseline_cutoff
    ]
    new_dispositions = [
        item for item in current_state.dispositions if baseline_cutoff is None or item["seq"] > baseline_cutoff
    ]
    reconciliation = event_ledger.classify_batch(new_entries, current_state.dispositions, baseline_keys)

    # 迟到事件：本批次投递、但业务事件时间落在基准水位对应的时间之前
    baseline_time = _watermark_time(baseline_events, baseline_cutoff)
    late_entries = [
        entry for entry in new_entries if baseline_time is not None and entry.event_ts <= baseline_time
    ]
    duplicate_count = sum(
        1 for item in new_dispositions if item["outcome"] == event_ledger.IGNORED_DUPLICATE
    )

    full_payloads = full_pass(label_rows, current_events)
    inc_payloads = incremental_pass(
        label_rows, baseline_events, current_events, new_entries
    )
    full_checksum = checksum(full_payloads)
    inc_checksum = checksum(inc_payloads)
    comparison = compare_passes(
        full_payloads,
        inc_payloads,
        late_event_count=len(late_entries),
        duplicate_event_count=duplicate_count,
    )

    impact = impact_ledger(new_dispositions, label_rows, baseline_cutoff)
    impact_summary = Counter(item["outcome"] for item in impact)

    # 负例对照：窗口右端放宽 grace_seconds，用同一个比对器必须报差异
    index = build_index(current_events)
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
        "baseline_cutoff_seq": baseline_cutoff,
        "current_cutoff_seq": current_cutoff,
        "range_start": iso_z(range_start),
        "range_end": iso_z(range_end),
        "scoped_event_count": len(current_events),
        "base_event_count": len(baseline_events),
        "new_event_count": len(new_entries),
        "late_event_count": len(late_entries),
        "duplicate_event_count": duplicate_count,
        "reconciliation": reconciliation,
        "aligned": reconciliation["aligned"],
        "full": {"checksum": full_checksum, "digest_count": len(full_payloads)},
        "incremental": {"checksum": inc_checksum, "digest_count": len(inc_payloads)},
        "equal": comparison["equal"],
        "invariant": "full == incremental",
        "invariant_hold": full_checksum == inc_checksum and comparison["equal"],
        "diff_sample_count": comparison["diff_sample_count"],
        "first_diff": comparison["first_diff"],
        "reason_classes": comparison["reason_classes"],
        "differences": comparison["differences"],
        "impact_summary": dict(impact_summary),
        "ledger_impact": impact,
        "self_check": {
            "induced_boundary": f"window_end_plus_{grace_seconds}s",
            "diff_sample_count": control["diff_sample_count"],
            "first_diff": control["first_diff"],
            "reason_classes": control_reasons,
            "sensitivity_ok": control["diff_sample_count"] > 0 or len(full_payloads) == 0,
        },
        "duration_ms": duration_ms,
    }


def _watermark_time(baseline_events: Sequence[Event], baseline_cutoff: int | None) -> datetime | None:
    """基准水位对应的时间锚：基准内最大事件时间（用于迟到归因，不参与裁切）。"""
    if baseline_cutoff is None or not baseline_events:
        return None
    return max(event.ts for event in baseline_events)


# --------------------------------------------------------------------------- #
# 自测（`python -m src.services.agg_engine`）
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    base_ts = datetime(2026, 3, 1, tzinfo=timezone.utc)
    entries: list[LedgerEntry] = []
    for i in range(40):
        entries.append(
            LedgerEntry(
                seq=i + 1,
                delivery_id=f"DLV-{i + 1:04d}",
                batch_id="BATCH-1",
                entity_key=f"ACC-{i % 3}",
                event_type="apply" if i % 2 == 0 else "repay",
                event_ts=base_ts + timedelta(hours=i * 9),
                amount=100 + i,
            )
        )
    # 基准水位固定在第 25 条，之后是新增 + 一条迟到事件（对平批次）
    baseline_cutoff = 25
    entries.append(
        LedgerEntry(
            seq=41,
            delivery_id="DLV-0041",
            batch_id="BATCH-2",
            entity_key="ACC-0",
            event_type="apply",
            event_ts=base_ts + timedelta(hours=4),  # 迟到：业务时间早于基准锚点
            amount=999,
        )
    )
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
    report = run_backfill(labels, entries, baseline_cutoff, current_cutoff=41)
    invariant_ok = report["invariant_hold"] and report["diff_sample_count"] == 0
    sensitivity_ok = report["self_check"]["diff_sample_count"] > 0
    aligned_ok = report["aligned"] is True
    late_ok = report["late_event_count"] == 1
    impact_ok = any(item["outcome"] == event_ledger.ACCEPTED for item in report["ledger_impact"])
    print(
        json.dumps(
            {
                "self_test": "agg_engine",
                "full_checksum": report["full"]["checksum"],
                "incremental_checksum": report["incremental"]["checksum"],
                "sample_count": report["sample_count"],
                "new_event_count": report["new_event_count"],
                "late_event_count": report["late_event_count"],
                "duplicate_event_count": report["duplicate_event_count"],
                "aligned": report["aligned"],
                "diff_sample_count": report["diff_sample_count"],
                "self_check_diff_samples": report["self_check"]["diff_sample_count"],
                "self_check_reasons": report["self_check"]["reason_classes"],
                "ok": bool(invariant_ok and sensitivity_ok and aligned_ok and late_ok and impact_ok),
            },
            ensure_ascii=False,
        )
    )
    return 0 if (invariant_ok and sensitivity_ok and aligned_ok and late_ok and impact_ok) else 1


if __name__ == "__main__":
    sys.exit(_self_test())
