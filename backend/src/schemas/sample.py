"""Sample job DTOs."""
from pydantic import BaseModel, Field

from src.constants.enums import BoundaryPolicy


class SampleJobCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    label_set_ids: list[int] = Field(min_length=1, max_length=4)
    feature_ids: list[int] = Field(min_length=1, max_length=12)
    range_start: str | None = None
    range_end: str | None = None
    boundary_policy: BoundaryPolicy | None = None


class SampleJobOut(BaseModel):
    id: int
    code: str
    name: str
    status: str
    label_set_ids: list[int]
    feature_ids: list[int]
    range_start: str | None
    range_end: str | None
    boundary_policy: str
    sample_count: int
    leak_count: int
    failure_reason: str | None
    created_by: str
    started_at: str | None
    finished_at: str | None
    created_at: str | None
    params_snapshot: dict
    leak_summary: dict | None = None
    leak_free: bool | None = None
