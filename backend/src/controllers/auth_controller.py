"""Auth handler logic (wired by app/routes/auth.py)."""
from src.services import auth_service


def login(db, email: str, password: str) -> dict:
    return auth_service.login(db, email, password)


def me(user) -> dict:
    return auth_service.me(user)
