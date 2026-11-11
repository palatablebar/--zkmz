"""Shared response envelopes + serialisation helpers."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def error_envelope(code: str, message: str, request_id: str | None, detail=None) -> dict:
    return {"code": code, "message": message, "detail": detail, "request_id": request_id}


def page(items: list, total: int, limit: int = 20, offset: int = 0) -> dict:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


class MessageOut(BaseModel):
    message: str
    detail: dict | None = None


def dt(value: datetime | None) -> str | None:
    from src.utils.timefmt import iso_z

    return iso_z(value)
