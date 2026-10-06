"""Stable API errors without exposing internal exception text."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]
    return error_response(422, "VALIDATION_ERROR", "Request validation failed", details)


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    response = error_response(
        exc.status_code, "HTTP_ERROR", "Request failed", jsonable_encoder(exc.detail)
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request error", exc_info=(type(exc), exc, exc.__traceback__))
    return error_response(500, "INTERNAL_ERROR", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, unexpected_error)
