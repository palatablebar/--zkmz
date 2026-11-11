"""Read-only catalogue DTOs: events / label sets / audit trail."""
from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    entity_key: str
    event_type: str
    event_ts: str
    amount: float
    channel: str
    source_ref: str


class LabelSetOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    sample_count: int
    entity_count: int
    label_positive: int
    first_label_time: str | None
    last_label_time: str | None


class AuditOut(BaseModel):
    id: int
    actor_email: str
    action: str
    entity_type: str
    entity_id: int | None
    created_at: str | None
    after_json: dict | None
