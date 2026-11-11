"""Auth router."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.schemas.auth import LoginOut, LoginRequest
from src.controllers import auth_controller

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_controller.login(db, payload.email, payload.password)


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return auth_controller.me(user)
