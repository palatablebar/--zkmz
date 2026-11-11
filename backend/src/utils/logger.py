"""Structured stdout logging (docker logs consumable)."""
import json
import logging
import sys

_LOGGER = logging.getLogger("featpoint")


def _ensure_handler() -> None:
    if _LOGGER.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)


def log_event(event: str, **fields) -> None:
    _ensure_handler()
    payload = {"event": event}
    payload.update({k: v for k, v in fields.items() if v is not None})
    _LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))
