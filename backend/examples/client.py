"""Typed synchronous dashboard client; older demo data uses latest anchoring."""

from types import TracebackType
from typing import Any, Literal
from urllib.parse import quote

import httpx

from app.schemas.alert import AlertOut
from app.schemas.common import Page
from app.schemas.maintenance import MaintenanceOut
from app.schemas.query import AnalyticsPoint, HealthPoint, TelemetryPoint, TrendOut
from app.schemas.state import LatestStateOut


class TwinClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8001", timeout: float = 30) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TwinClient":
        return self

    def __exit__(self, *args: type[BaseException] | BaseException | TracebackType | None) -> None:
        self.close()

    def _get(self, asset: str, suffix: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(
            "/api/v1/transformers/" + quote(asset, safe="") + "/" + suffix, params=params
        )
        response.raise_for_status()
        return response.json()

    def latest(self, asset: str = "TX-001") -> LatestStateOut:
        return LatestStateOut.model_validate(self._get(asset, "latest"))

    def telemetry(
        self,
        asset: str = "TX-001",
        *,
        limit: int = 500,
        offset: int = 0,
        order: Literal["asc", "desc"] = "asc",
        fields: str | None = None,
    ) -> Page[TelemetryPoint]:
        params: dict[str, Any] = {
            "anchor": "latest",
            "limit": limit,
            "offset": offset,
            "order": order,
        }
        if fields is not None:
            params["fields"] = fields
        return Page[TelemetryPoint].model_validate(self._get(asset, "telemetry", params))

    def health(
        self,
        asset: str = "TX-001",
        *,
        limit: int = 500,
        offset: int = 0,
        order: Literal["asc", "desc"] = "asc",
    ) -> Page[HealthPoint]:
        return Page[HealthPoint].model_validate(
            self._get(
                asset,
                "health",
                {"anchor": "latest", "limit": limit, "offset": offset, "order": order},
            )
        )

    def analytics(
        self,
        asset: str = "TX-001",
        *,
        limit: int = 500,
        offset: int = 0,
        order: Literal["asc", "desc"] = "asc",
    ) -> Page[AnalyticsPoint]:
        return Page[AnalyticsPoint].model_validate(
            self._get(
                asset,
                "analytics",
                {"anchor": "latest", "limit": limit, "offset": offset, "order": order},
            )
        )

    def alerts(
        self,
        asset: str = "TX-001",
        *,
        limit: int = 500,
        offset: int = 0,
        status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"] | None = None,
        severity: Literal["INFO", "WARNING", "CRITICAL"] | None = None,
    ) -> Page[AlertOut]:
        params: dict[str, Any] = {"anchor": "latest", "limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if severity is not None:
            params["severity"] = severity
        return Page[AlertOut].model_validate(self._get(asset, "alerts", params))

    def maintenance(
        self,
        asset: str = "TX-001",
        *,
        limit: int = 500,
        offset: int = 0,
        status: Literal["OPEN", "DONE", "DISMISSED"] | None = None,
    ) -> Page[MaintenanceOut]:
        params: dict[str, Any] = {"anchor": "latest", "limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        return Page[MaintenanceOut].model_validate(self._get(asset, "maintenance", params))

    def trends(
        self,
        asset: str = "TX-001",
        *,
        signals: str = "oil_temperature,health_index,fault_risk",
        window: Literal["1h", "6h", "24h", "7d"] = "24h",
    ) -> TrendOut:
        return TrendOut.model_validate(
            self._get(asset, "trends", {"anchor": "latest", "signals": signals, "window": window})
        )


if __name__ == "__main__":
    with TwinClient() as twin:
        print(twin.latest().model_dump_json(indent=2))
