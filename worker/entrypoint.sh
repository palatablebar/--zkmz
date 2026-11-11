#!/usr/bin/env bash
# 等 PostgreSQL / Redis 就绪 → 起心跳 → 起 Celery worker（队列 featpoint）。
set -euo pipefail

echo "[worker] waiting for db/redis ..."
python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from redis import Redis
from src.config.settings import settings

for attempt in range(60):
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Redis.from_url(settings.REDIS_URL, socket_timeout=1).ping()
        print("[worker] db and redis are ready", flush=True)
        sys.exit(0)
    except Exception as exc:
        if attempt % 5 == 0:
            print(f"[worker] not ready ({type(exc).__name__}); retrying", flush=True)
        time.sleep(3)
print("[worker] dependencies never became ready", flush=True)
sys.exit(1)
PY

# 心跳文件给 compose healthcheck 用（worker/healthy.py）
( while true; do date +%s > /tmp/featpoint-worker-heartbeat; sleep 5; done ) &

exec celery -A src.config.celery_app worker \
  --loglevel=info \
  --concurrency=2 \
  --hostname=featpoint-worker@%h \
  --without-gossip --without-mingle --without-heartbeat \
  -Q featpoint
