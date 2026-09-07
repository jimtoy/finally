"""Uniform error responses: {"detail": ..., "code": ...} (PLAN.md sec 8)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """A business-rule failure with a stable error code."""

    def __init__(self, detail: str, code: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


def _payload(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


_STATUS_CODES = {400: "bad_request", 404: "not_found", 502: "upstream_error"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(exc.detail, exc.code))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ())[1:])
        message = first.get("msg", "Invalid request body")
        detail = f"{location}: {message}" if location else message
        return JSONResponse(status_code=422, content=_payload(detail, "validation_error"))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_payload(str(exc.detail), code))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500, content=_payload("Internal server error", "internal_error")
        )
