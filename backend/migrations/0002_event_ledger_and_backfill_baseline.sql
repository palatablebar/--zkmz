-- 演进：事件投递台账 + 回填基准水位（对应模型 event_ledger.EventLedger /
-- backfill.BackfillTask 新列）。运行期仍由 SQLAlchemy create_all 幂等建表，
-- 本文件是 PostgreSQL 16 参考 DDL，与模型保持一一对照。

-- 1) append-only 事件投递台账：每行 = 上游一次投递（upsert/retract），
--    delivery_id 唯一保证重复投递在落库层就无法二次生效。
CREATE TABLE IF NOT EXISTS event_ledger (
    id          BIGSERIAL PRIMARY KEY,
    seq         BIGINT       NOT NULL UNIQUE,
    delivery_id VARCHAR(64)  NOT NULL UNIQUE,
    batch_id    VARCHAR(64)  NOT NULL DEFAULT '',
    entity_key  VARCHAR(48)  NOT NULL,
    event_type  VARCHAR(16)  NOT NULL,
    event_ts    TIMESTAMPTZ  NOT NULL,
    action      VARCHAR(16)  NOT NULL DEFAULT 'upsert',
    amount      NUMERIC(14,2) NOT NULL DEFAULT 0,
    channel     VARCHAR(16)  NOT NULL DEFAULT 'app',
    source_ref  VARCHAR(64)  NOT NULL DEFAULT '',
    is_seed     BOOLEAN      NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_event_ledger_seq ON event_ledger (seq);
CREATE INDEX IF NOT EXISTS ix_event_ledger_batch ON event_ledger (batch_id);
CREATE INDEX IF NOT EXISTS ix_event_ledger_entity ON event_ledger (entity_key);
CREATE INDEX IF NOT EXISTS ix_event_ledger_ts ON event_ledger (event_ts);

-- 2) 回填任务基准从「范围中点时间」改为「上次成功运行的台账 seq 水位」。
ALTER TABLE backfill_task
    ADD COLUMN IF NOT EXISTS baseline_cutoff_seq BIGINT,
    ADD COLUMN IF NOT EXISTS baseline_event_count INTEGER;
-- base_watermark 保留（历史报告展示用），新运行不再按它切分事件。
