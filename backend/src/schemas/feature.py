"""Feature definition DTOs (window/boundary/aggregate are validated here)."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.constants.enums import AggregateKind, BoundaryPolicy, EventType

WindowLabel = Literal["1d", "7d", "30d"]
WINDOW_SECONDS = {"1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


class FeatureCreate(BaseModel):
    code: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=400)
    event_type: EventType | None = None
    amount_min: float | None = Field(default=None, ge=0, le=10_000_000)
    window_label: WindowLabel
    boundary_policy: BoundaryPolicy = BoundaryPolicy.STRICT
    aggregate_kind: AggregateKind

    @field_validator("aggregate_kind")
    @classmethod
    def aggregate_allowed(cls, value: AggregateKind) -> AggregateKind:
        return value


class FeatureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    event_type: EventType | None = None
    amount_min: float | None = Field(default=None, ge=0, le=10_000_000)
    window_label: WindowLabel | None = None
    boundary_policy: BoundaryPolicy | None = None
    aggregate_kind: AggregateKind | None = None
    change_note: str = Field(default="", max_length=255)


class FeatureOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    event_type: str | None
    amount_min: float | None
    window_seconds: int
    window_label: str
    boundary_policy: str
    aggregate_kind: str
    status: str
    version: int
    owner_id: int | None
    published_at: str | None
    updated_at: str | None
    dsl: str


class FeatureVersionOut(BaseModel):
    id: int
    version_no: int
    change_note: str
    changed_by: str
    snapshot: dict
    created_at: str | None
