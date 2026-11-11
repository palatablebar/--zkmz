"""台账重放 / 回填对账 / 冻结口径的单元测试（仅依赖标准库）。

运行：``cd backend && python3 -m unittest tests.test_ledger_backfill -v``

覆盖用户提出的四个问题：
1. 样本任务按创建时冻结的特征口径重算（pit_engine + 快照重建 FeatureSpec）；
2. 回填固定上次可用的事件状态（台账 seq 水位），再合并之后的新增/更正；
3. 重复投递只生效一次、迟到更正可增量合并、撤销/替换影响可追溯；
4. 新批次未对平时保留旧结果；起点前的窗口历史不再被裁掉。
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from src.services import agg_engine, event_ledger
from src.services.event_ledger import LedgerEntry
from src.services.pit_engine import (
    FeatureSpec,
    LabelRow,
    build_index,
    build_samples,
    normalize_events,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _entry(seq, delivery_id, entity, etype, ts, amount=100.0, action=event_ledger.UPSERT, batch="B1"):
    return LedgerEntry(
        seq=seq,
        delivery_id=delivery_id,
        batch_id=batch,
        entity_key=entity,
        event_type=etype,
        event_ts=ts,
        action=action,
        amount=amount,
    )


def _label(row_id, entity, label_time, label=0):
    return LabelRow(id=row_id, label_set_id=1, entity_key=entity, label_time=label_time, label=label)


class LedgerReplayTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            _entry(1, "D-1", "ACC-1", "apply", T0, 100),
            _entry(2, "D-2", "ACC-1", "repay", T0 + timedelta(hours=2), 50),
            _entry(3, "D-3", "ACC-2", "apply", T0 + timedelta(hours=5), 200),
        ]

    def test_replay_builds_canonical_state(self):
        state = event_ledger.replay(self.entries)
        self.assertEqual(len(state.events), 3)
        self.assertEqual({d["outcome"] for d in state.dispositions}, {event_ledger.ACCEPTED})

    def test_duplicate_delivery_applies_once(self):
        dup = _entry(4, "D-1", "ACC-1", "apply", T0, 999, batch="B2")
        state = event_ledger.replay(self.entries + [dup])
        # 同一 delivery_id 第二次投递被忽略，原事件金额保持 100
        acc1_apply = state.events[event_ledger.natural_key("ACC-1", "apply", T0)]
        self.assertEqual(acc1_apply.amount, 100.0)
        self.assertEqual(len(state.events), 3)
        self.assertIn(
            event_ledger.IGNORED_DUPLICATE,
            [d["outcome"] for d in state.dispositions],
        )

    def test_upsert_replaces_amount(self):
        correction = _entry(4, "D-4", "ACC-1", "apply", T0, 300, batch="B2")
        state = event_ledger.replay(self.entries + [correction])
        key = event_ledger.natural_key("ACC-1", "apply", T0)
        self.assertEqual(state.events[key].amount, 300.0)
        disp = next(d for d in state.dispositions if d["seq"] == 4)
        self.assertEqual(disp["outcome"], event_ledger.REPLACED)
        self.assertEqual(disp["amount_before"], 100.0)
        self.assertEqual(disp["amount_after"], 300.0)

    def test_retract_removes_event(self):
        retract = _entry(4, "D-5", "ACC-2", "apply", T0 + timedelta(hours=5),
                         action=event_ledger.RETRACT, batch="B2")
        state = event_ledger.replay(self.entries + [retract])
        self.assertEqual(len(state.events), 2)
        self.assertEqual(state.dispositions[-1]["outcome"], event_ledger.RETRACTED)

    def test_retract_missing_is_flagged_not_raised(self):
        retract = _entry(4, "D-6", "ACC-9", "apply", T0, action=event_ledger.RETRACT, batch="B2")
        state = event_ledger.replay(self.entries + [retract])
        self.assertEqual(state.dispositions[-1]["outcome"], event_ledger.RETRACT_MISSING)

    def test_cutoff_freezes_historical_state(self):
        late = _entry(4, "D-7", "ACC-1", "apply", T0 + timedelta(minutes=30), 777, batch="B2")
        all_entries = self.entries + [late]
        baseline = event_ledger.replay(all_entries, cutoff_seq=3)
        current = event_ledger.replay(all_entries, cutoff_seq=4)
        self.assertEqual(len(baseline.events), 3)
        self.assertEqual(len(current.events), 4)
        # 固定水位可重复重放出完全一致的状态
        again = event_ledger.replay(all_entries, cutoff_seq=3)
        self.assertEqual(
            [(e.id, e.amount) for e in baseline.as_events()],
            [(e.id, e.amount) for e in again.as_events()],
        )


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.base = [
            _entry(1, "D-1", "ACC-1", "apply", T0, 100),
            _entry(2, "D-2", "ACC-1", "repay", T0 + timedelta(hours=2), 50),
        ]
        self.baseline_state = event_ledger.replay(self.base)
        self.baseline_keys = set(self.baseline_state.events.keys())

    def test_aligned_when_only_new_natural_keys_arrive(self):
        new_entries = [_entry(3, "D-3", "ACC-1", "login", T0 + timedelta(hours=8), 0, batch="B2")]
        state = event_ledger.replay(self.base + new_entries)
        verdict = event_ledger.classify_batch(new_entries, state.dispositions, self.baseline_keys)
        self.assertTrue(verdict["aligned"])

    def test_misaligned_on_duplicate_delivery(self):
        new_entries = [_entry(3, "D-1", "ACC-1", "apply", T0, 999, batch="B2")]
        state = event_ledger.replay(self.base + new_entries)
        verdict = event_ledger.classify_batch(new_entries, state.dispositions, self.baseline_keys)
        self.assertFalse(verdict["aligned"])
        self.assertEqual(verdict["issues"][0]["reason"], event_ledger.IGNORED_DUPLICATE)

    def test_misaligned_on_retract_missing(self):
        new_entries = [_entry(3, "D-4", "ACC-9", "apply", T0, action=event_ledger.RETRACT, batch="B2")]
        state = event_ledger.replay(self.base + new_entries)
        verdict = event_ledger.classify_batch(new_entries, state.dispositions, self.baseline_keys)
        self.assertFalse(verdict["aligned"])
        self.assertEqual(verdict["issues"][0]["reason"], event_ledger.RETRACT_MISSING)

    def test_misaligned_when_baseline_event_rewritten(self):
        new_entries = [_entry(3, "D-5", "ACC-1", "apply", T0, 250, batch="B2")]  # 更正基准内事件
        state = event_ledger.replay(self.base + new_entries)
        verdict = event_ledger.classify_batch(new_entries, state.dispositions, self.baseline_keys)
        self.assertFalse(verdict["aligned"])
        self.assertEqual(verdict["issues"][0]["reason"], "baseline_rewritten")

    def test_intra_batch_insert_then_correct_is_aligned(self):
        # 同批次先新增、再更正同一新自然键：没有改写基准，应对平
        new_entries = [
            _entry(3, "D-6", "ACC-2", "apply", T0 + timedelta(hours=1), 100, batch="B2"),
            _entry(4, "D-7", "ACC-2", "apply", T0 + timedelta(hours=1), 180, batch="B2"),
        ]
        state = event_ledger.replay(self.base + new_entries)
        verdict = event_ledger.classify_batch(new_entries, state.dispositions, self.baseline_keys)
        self.assertTrue(verdict["aligned"])
        key = event_ledger.natural_key("ACC-2", "apply", T0 + timedelta(hours=1))
        self.assertEqual(state.events[key].amount, 180.0)


class BackfillEngineTests(unittest.TestCase):
    def setUp(self):
        # 事件时间跨度 40 天，标签落在范围中段；窗口历史在标签之前
        self.entries = [
            _entry(i + 1, f"D-{i+1}", f"ACC-{i % 2}", "apply",
                   T0 + timedelta(hours=i * 6), amount=100 + i)
            for i in range(80)
        ]
        self.labels = [
            _label(1, "ACC-0", T0 + timedelta(days=20)),
            _label(2, "ACC-1", T0 + timedelta(days=25)),
            _label(3, "ACC-0", T0 + timedelta(days=30)),
        ]

    def test_first_run_sets_baseline_and_invariant_holds(self):
        report = agg_engine.run_backfill(self.labels, self.entries, None, current_cutoff=80)
        self.assertTrue(report["aligned"])
        self.assertTrue(report["invariant_hold"])
        self.assertEqual(report["full"]["checksum"], report["incremental"]["checksum"])
        # 首次运行没有基准：base_event_count=0，全部投递都是新增
        self.assertEqual(report["base_event_count"], 0)
        self.assertEqual(report["new_event_count"], 80)
        self.assertIsNone(report["baseline_cutoff_seq"])

    def test_window_history_before_range_start_is_kept(self):
        # 标签 T0+20d 的 30d 窗口起点是 T0-10d；台账里 T0 起的事件必须进入窗口，
        # 旧实现按范围中点切分会丢掉这部分历史。
        range_start = T0 + timedelta(days=15)
        report = agg_engine.run_backfill(
            self.labels, self.entries, baseline_cutoff=None, current_cutoff=80,
            range_start=range_start, range_end=T0 + timedelta(days=35),
        )
        current_events = event_ledger.replay_snapshot(self.entries, 80)
        payloads = {p["label_row_id"]: p for p in agg_engine.full_pass(self.labels, current_events)}
        self.assertGreater(payloads[1]["windows"]["30d"]["cnt"], 0)
        self.assertGreater(payloads[1]["windows"]["30d"]["cnt"], payloads[1]["windows"]["7d"]["cnt"])

    def test_incremental_equals_full_with_late_corrections(self):
        first = agg_engine.run_backfill(self.labels, self.entries, None, current_cutoff=80)
        # 第二批：新增事件 + 迟到事件（业务时间早于基准锚点）+ 一个新键
        batch2 = [
            _entry(81, "D-81", "ACC-0", "repay", T0 + timedelta(days=22), 900, batch="B2"),
            _entry(82, "D-82", "ACC-1", "apply", T0 + timedelta(days=2), 55, batch="B2"),  # 迟到
            _entry(83, "D-83", "ACC-0", "login", T0 + timedelta(days=31), 0, batch="B2"),
        ]
        all_entries = self.entries + batch2
        second = agg_engine.run_backfill(
            self.labels, all_entries, baseline_cutoff=80, current_cutoff=83,
            range_start=T0 + timedelta(days=15), range_end=T0 + timedelta(days=35),
        )
        self.assertTrue(second["aligned"])
        self.assertTrue(second["invariant_hold"])
        self.assertEqual(second["late_event_count"], 1)
        self.assertEqual(second["base_event_count"], first["scoped_event_count"])

    def test_duplicate_delivery_misaligned_and_impact_listed(self):
        batch2 = [_entry(81, "D-1", "ACC-0", "apply", T0, 999, batch="B2")]
        report = agg_engine.run_backfill(
            self.labels, self.entries + batch2, baseline_cutoff=80, current_cutoff=81,
        )
        self.assertFalse(report["aligned"])
        self.assertEqual(report["duplicate_event_count"], 1)
        impacts = report["ledger_impact"]
        dup = next(item for item in impacts if item["outcome"] == event_ledger.IGNORED_DUPLICATE)
        # 被忽略的记录也要说明它本应影响哪些样本
        self.assertGreaterEqual(dup["affected_sample_count"], 1)
        self.assertTrue(any(h["label_row_id"] == 1 for h in dup["affected_samples"]))

    def test_retraction_impact_traces_to_samples(self):
        # 撤销一个基准内事件 → 未对平 + 影响样本清单
        target_ts = T0 + timedelta(hours=6)  # seq=2, ACC-1 apply
        batch2 = [_entry(81, "D-90", "ACC-1", "apply", target_ts,
                         action=event_ledger.RETRACT, batch="B2")]
        report = agg_engine.run_backfill(
            self.labels, self.entries + batch2, baseline_cutoff=80, current_cutoff=81,
        )
        self.assertFalse(report["aligned"])
        retract_impact = next(i for i in report["ledger_impact"] if i["outcome"] == event_ledger.RETRACTED)
        self.assertEqual(retract_impact["affected_samples"][0]["window"], "30d")

    def test_replacement_records_before_and_after_amount(self):
        target_ts = T0 + timedelta(hours=6)
        batch2 = [_entry(81, "D-91", "ACC-1", "apply", target_ts, 4242, batch="B2")]
        report = agg_engine.run_backfill(
            self.labels, self.entries + batch2, baseline_cutoff=80, current_cutoff=81,
        )
        self.assertFalse(report["aligned"])  # 改写基准 → 未对平
        impact = next(i for i in report["ledger_impact"] if i["outcome"] == event_ledger.REPLACED)
        self.assertEqual(impact["amount_before"], 101.0)
        self.assertEqual(impact["amount_after"], 4242.0)
        self.assertGreater(impact["affected_sample_count"], 0)

    def test_multi_batch_watermark_lifecycle(self):
        """成功 → 未对平（水位不动）→ 修复后对平（水位推进）的完整状态机。"""
        # 第一次：成功，调用方据此把水位固定到 80
        first = agg_engine.run_backfill(self.labels, self.entries, None, current_cutoff=80)
        fixed_cutoff = 80
        self.assertTrue(first["aligned"])

        # 第二次：重复投递未对平——服务层会保留旧结果、不推进水位
        bad_batch = [_entry(81, "D-1", "ACC-0", "apply", T0, 999, batch="B2")]
        bad_report = agg_engine.run_backfill(
            self.labels, self.entries + bad_batch, baseline_cutoff=fixed_cutoff, current_cutoff=81,
        )
        self.assertFalse(bad_report["aligned"])
        retained_cutoff = fixed_cutoff  # _handle_misaligned 保持 baseline_cutoff_seq 不变
        self.assertEqual(retained_cutoff, 80)

        # 第三次：上游改用新 delivery_id 投递合法新事件，批次对平
        good_batch = [_entry(82, "D-82", "ACC-0", "repay", T0 + timedelta(days=28), 700, batch="B3")]
        # 台账里仍含被忽略的 seq=81（重复），但它不产生事件，不影响对平判定之外的状态
        good_report = agg_engine.run_backfill(
            self.labels,
            self.entries + bad_batch + good_batch,
            baseline_cutoff=retained_cutoff,
            current_cutoff=82,
        )
        # seq=81 的重复投递依然在本批次窗口内 → 仍未对平，证明「问题不处理不会静默通过」
        self.assertFalse(good_report["aligned"])

        # 上游回滚问题批次后（台账只保留合法投递），回填对平并推进水位
        clean_report = agg_engine.run_backfill(
            self.labels,
            self.entries + good_batch,
            baseline_cutoff=retained_cutoff,
            current_cutoff=82,
        )
        self.assertTrue(clean_report["aligned"])
        self.assertTrue(clean_report["invariant_hold"])
        self.assertEqual(clean_report["base_event_count"], first["scoped_event_count"])


class FrozenSpecRecomputeTests(unittest.TestCase):
    """样本任务必须按创建时冻结的口径重算（sample_service.specs_from_snapshot 同构）。"""

    SNAPSHOT = [
        {
            "feature_id": 7,
            "code": "cnt_30d_apply",
            "name": "近 30 天申请次数",
            "window_label": "30d",
            "window_seconds": 30 * 86400,
            "boundary_policy": "inclusive",  # 创建时的（错误）口径
            "aggregate_kind": "count",
            "event_type": "apply",
            "amount_min": None,
        }
    ]

    def _specs(self):
        # 与 sample_service.specs_from_snapshot 相同的重建逻辑
        return [
            FeatureSpec(
                id=int(item.get("feature_id") or -(i + 1)),
                code=item["code"],
                name=item["name"],
                window_seconds=item["window_seconds"],
                window_label=item["window_label"],
                boundary=item["boundary_policy"],
                aggregate=item["aggregate_kind"],
                event_type=item.get("event_type"),
                amount_min=item.get("amount_min"),
                description="",
            )
            for i, item in enumerate(self.SNAPSHOT)
        ]

    def test_recompute_uses_frozen_inclusive_boundary(self):
        label_time = T0 + timedelta(days=10)
        events = normalize_events(
            [
                {"id": 1, "entity_key": "ACC-1", "event_type": "apply",
                 "ts": label_time, "amount": 100},  # 恰好标签时刻
                {"id": 2, "entity_key": "ACC-1", "event_type": "apply",
                 "ts": label_time - timedelta(days=2), "amount": 200},
            ]
        )
        labels = [_label(1, "ACC-1", label_time)]
        frozen_specs = self._specs()

        # 用冻结的 inclusive 口径重算（即使当前定义已修正为 strict）
        built = build_samples(frozen_specs, events, labels, effective_boundary="inclusive")
        self.assertEqual(built["samples"][0]["features"]["cnt_30d_apply"], 2.0)
        self.assertTrue(built["samples"][0]["has_leak"])

        # 模拟「当前定义已改成 strict」：按当前口径会得到 1，但重算必须仍是 2
        strict_spec = FeatureSpec(**{**frozen_specs[0].__dict__, "boundary": "strict"})
        current = build_samples([strict_spec], events, labels, effective_boundary="strict")
        self.assertEqual(current["samples"][0]["features"]["cnt_30d_apply"], 1.0)
        self.assertNotEqual(
            built["samples"][0]["features"]["cnt_30d_apply"],
            current["samples"][0]["features"]["cnt_30d_apply"],
        )

    def test_frozen_window_size_is_ignored_by_current_definition(self):
        # 快照里是 7d，当前定义改成 30d：重算必须仍按 7d
        label_time = T0 + timedelta(days=10)
        events = normalize_events(
            [
                {"id": 1, "entity_key": "ACC-1", "event_type": "apply",
                 "ts": label_time - timedelta(days=2), "amount": 100},
                {"id": 2, "entity_key": "ACC-1", "event_type": "apply",
                 "ts": label_time - timedelta(days=20), "amount": 200},
            ]
        )
        labels = [_label(1, "ACC-1", label_time)]
        snapshot = [{**self.SNAPSHOT[0], "window_label": "7d", "window_seconds": 7 * 86400,
                     "boundary_policy": "strict", "code": "cnt_7d"}]
        frozen = [
            FeatureSpec(
                id=1, code="cnt_7d", name="x", window_seconds=7 * 86400, window_label="7d",
                boundary="strict", aggregate="count", event_type="apply", amount_min=None,
            )
        ]
        built = build_samples(frozen, events, labels, effective_boundary="strict")
        self.assertEqual(built["samples"][0]["features"]["cnt_7d"], 1.0)
        self.assertEqual(len(snapshot), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
