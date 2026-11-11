"""Role checks as FastAPI dependencies.

``require_roles("owner")`` on a router function yields a 403 whose detail names
the allowed roles. Denials never mutate state (they are raised before the
controller body runs).
"""
from fastapi import Depends

from src.constants.enums import Role
from src.constants.error_codes import AppError, ErrorCode
from src.middlewares.auth import get_current_user
from src.models import User

WRITE_ROLES = (Role.OWNER.value,)
SAMPLE_ROLES = (Role.OWNER.value, Role.ANALYST.value)
READ_ROLES = (Role.OWNER.value, Role.ANALYST.value, Role.VIEWER.value)


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(
                ErrorCode.FORBIDDEN,
                message=f"当前角色 {user.role} 无权执行该操作，需要 {'/'.join(roles)}",
                detail={"required_roles": list(roles), "role": user.role},
            )
        return user

    return dependency


def require_owner(user: User = Depends(require_roles(*WRITE_ROLES))) -> User:
    return user


def require_sample_editor(user: User = Depends(require_roles(*SAMPLE_ROLES))) -> User:
    return user


def require_reader(user: User = Depends(require_roles(*READ_ROLES))) -> User:
    return user


def can_write(user: User) -> bool:
    return user.role == Role.OWNER.value
