"""UTC normalisation + the canonical timestamp form used in payloads.

Every timestamp is stored timezone-aware (UTC) and serialised as ISO-8601 with
a trailing ``Z``. Parsing accepts ISO-8601, ``YYYY-MM-DD HH:MM:SS`` and epoch
seconds; anything else raises BadTimestamp so the PIT engine can fail the job
with reason ``bad_timestamp``.
"""
from datetime import datetime, timezone

from src.constants.error_codes import AppError, ErrorCode


class BadTimestamp(Exception):
    pass


def parse_ts(value) -> datetime:
    """Parse into an aware UTC datetime. Raises BadTimestamp."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise BadTimestamp("空时间戳")
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            except ValueError as exc:
                raise BadTimestamp(f"无法解析时间戳: {value!r}") from exc
    else:
        raise BadTimestamp(f"不支持的时间戳类型: {type(value).__name__}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ms_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ts_or_fail(value) -> datetime:
    try:
        return parse_ts(value)
    except BadTimestamp as exc:
        raise AppError(ErrorCode.BAD_TIMESTAMP, detail={"value": str(value)}) from exc
