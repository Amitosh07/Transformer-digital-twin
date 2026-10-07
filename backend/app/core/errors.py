"""Stable API errors without exposing internal exception text."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message, details=details),
        ).model_dump(mode="json"),
    )


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]
    return correlated_error(request, 422, "VALIDATION_ERROR", "Request validation failed", details)


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    response = correlated_error(
        request,
        exc.status_code,
        "HTTP_ERROR",
        "Request failed",
        jsonable_encoder(exc.detail) if exc.status_code < 500 else None,
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request error error_type=%s", type(exc).__name__)
    return correlated_error(request, 500, "INTERNAL_ERROR", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, unexpected_error)


def correlated_error(
    request: Request, status: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        if isinstance(details, list):
            details = [*details, {"request_id": request_id}]
        elif isinstance(details, dict):
            details = details | {"request_id": request_id}
        elif details is None:
            details = {"request_id": request_id}
        else:
            details = {"message": details, "request_id": request_id}
    response = error_response(status, code, message, details)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response
