"""Auth + quota DTOs."""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    role_label: str


class QuotaOut(BaseModel):
    daily_quota: int
    quota_used: int
    quota_remaining: int
    rate_window_seconds: int
    rate_window_max: int


class LoginOut(BaseModel):
    token: str
    user: UserOut
    quota: QuotaOut
