"""Login + daily quota reset."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.error_codes import AppError, ErrorCode
from src.middlewares import quota as quota_middleware
from src.models import User
from src.utils.jwt import create_access_token
from src.utils.logger import log_event
from src.utils.password import verify_password
from src.utils.serialize import user_out


def reset_daily_quota_if_needed(db: Session, user: User) -> None:
    today = date.today()
    if user.quota_date != today:
        user.quota_date = today
        user.quota_used = 0
        db.commit()


def login(db: Session, email: str, password: str) -> dict:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        log_event("LOGIN_FAILED", email=email)
        raise AppError(ErrorCode.UNAUTHORIZED, message="邮箱或密码不正确")
    reset_daily_quota_if_needed(db, user)
    log_event("LOGIN_OK", email=user.email, role=user.role)
    return {
        "token": create_access_token(user),
        "user": user_out(user),
        "quota": quota_middleware.quota_snapshot(user),
    }


def me(user: User) -> dict:
    return {"user": user_out(user), "quota": quota_middleware.quota_snapshot(user)}
