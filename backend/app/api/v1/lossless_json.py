"""Preserve source Decimal precision before FastAPI/Pydantic float coercion."""
from fastapi import Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError


class LosslessJSONRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request: Request):
            if request.headers.get('content-type', '').split(';')[0].strip() == 'application/json':
                from ml.pipeline.identity import parse_record_json
                try:
                    request._json = parse_record_json(await request.body())
                except (ValueError, UnicodeDecodeError):
                    raise RequestValidationError([{'loc': ('body',), 'msg': 'Invalid JSON', 'type': 'json_invalid'}]) from None
            return await original(request)
        return handle
