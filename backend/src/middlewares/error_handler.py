"""Uniform error envelope + request-id propagation."""
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.constants.error_codes import AppError, ErrorCode
from src.schemas.common import error_envelope
from src.utils.logger import log_event


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        log_event(
            "APP_ERROR",
            code=exc.code,
            status=exc.status_code,
            path=request.url.path,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                exc.code, exc.message, getattr(request.state, "request_id", None), exc.detail
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                ErrorCode.VALIDATION_FAILED.value,
                "请求参数校验失败",
                getattr(request.state, "request_id", None),
                {"errors": exc.errors()[:8]},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        log_event("UNHANDLED_ERROR", path=request.url.path, error=f"{type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                "FP-5000",
                "服务内部错误",
                getattr(request.state, "request_id", None),
                {"error": f"{type(exc).__name__}"},
            ),
        )
