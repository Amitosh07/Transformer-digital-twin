"""Shared validation rules and public response envelopes."""

from collections.abc import Mapping
from datetime import UTC, datetime
import re
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
MaintenancePriority = Literal["NORMAL", "WATCH", "PLAN", "URGENT"]
ReasonCode = Literal[
    "HIGH_OIL_TEMP",
    "RAPID_TEMP_RISE",
    "OVERLOAD",
    "CURRENT_IMBALANCE",
    "VOLTAGE_IMBALANCE",
    "LOW_OIL_LEVEL",
    "OIL_TEMP_ALARM",
    "OIL_TEMP_TRIP",
    "MOG_ALARM",
    "ANOMALOUS_PATTERN",
]


def require_datetime_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("Timestamp must be an ISO-8601 string or aware datetime")
    if isinstance(value, str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('Aware ISO timestamp at microsecond precision required')
    return value


def normalize_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[
    AwareDatetime,
    BeforeValidator(require_datetime_input),
    AfterValidator(normalize_utc),
]


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def reject_excluded_fields(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            for key in value:
                if isinstance(key, str):
                    normalized = "".join(char for char in key.casefold() if char.isalnum())
                    if normalized in {"vl12", "vl23", "vl31"}:
                        raise ValueError(f"Field {key!r} is excluded from the canonical schema")
        return value


T = TypeVar("T")


class Page(CanonicalModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class ErrorDetail(CanonicalModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(CanonicalModel):
    error: ErrorDetail
