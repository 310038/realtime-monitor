"""統一錯誤格式：{"error": {"code", "message", "details"}}。"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppException(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: object = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status.HTTP_404_NOT_FOUND, "NOT_FOUND", f"{resource} not found")


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message)


class BadRequestError(AppException):
    def __init__(self, message: str, details: object = None):
        super().__init__(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", message, details)


def _error(status_code: int, code: str, message: str, details: object = None, headers=None):
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(_: Request, exc: AppException):
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "HTTP_ERROR", str(exc.detail), headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError):
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(IntegrityError)
    async def _integrity_exc(_: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", exc.orig)
        return _error(status.HTTP_409_CONFLICT, "CONFLICT", "Data integrity violation")

    @app.exception_handler(SQLAlchemyError)
    async def _db_exc(_: Request, exc: SQLAlchemyError):
        logger.exception("Database error")
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_ERROR", "Database error")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Internal server error")
