"""统一异常体系：AppError 层级 + FastAPI 全局 handler 注册。"""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """业务异常基类。code 为业务错误码(5位)，http_status 为 HTTP 状态码。"""

    code: int = 50000
    http_status: int = 500

    def __init__(self, message: str = "", *, code: int | None = None, http_status: int | None = None, data: Any = None):
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.data = data
        super().__init__(self.message)


class NotFoundError(AppError):
    code = 40400
    http_status = 404


class AuthError(AppError):
    code = 40100
    http_status = 401


class PermError(AppError):
    code = 40300
    http_status = 403


class ConflictError(AppError):
    code = 40900
    http_status = 409


class ValidationAppError(AppError):
    code = 42200
    http_status = 422


class SSHConnectError(AppError):
    code = 50201
    http_status = 502


def register_exception_handlers(app: FastAPI) -> None:
    from app.core.response import error

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=error(exc.code, exc.message, exc.data))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        msg = f"{first.get('loc', '')}: {first.get('msg', '参数错误')}"
        return JSONResponse(status_code=422, content=error(42200, msg))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content=error(50000, "服务器内部错误"))
