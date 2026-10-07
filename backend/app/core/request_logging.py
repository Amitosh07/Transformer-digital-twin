"""ASGI request metadata logging without bodies, query strings or telemetry values."""

import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import unexpected_error

logger = logging.getLogger(__name__)
SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("x-request-id", "")
        request_id = supplied if SAFE_ID.fullmatch(supplied) else str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        status = 500
        started = False
        start = perf_counter()

        async def response_send(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                status, started = message["status"], True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, response_send)
        except Exception as exc:
            if started:
                raise
            response = await unexpected_error(Request(scope), exc)
            await response(scope, receive, response_send)
        finally:
            duration_ms = round((perf_counter() - start) * 1000, 3)
            logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.3f",
                request_id,
                scope["method"],
                scope["path"],
                status,
                duration_ms,
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
