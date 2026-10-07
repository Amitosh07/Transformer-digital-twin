from typing import Literal

from pydantic import Field

from app.schemas.common import CanonicalModel


class ReadinessOut(CanonicalModel):
    status: Literal["ready", "not_ready"]
    db: Literal["ready", "error"]
    migrations: Literal["ready", "error"]
    ml: Literal["ready", "unchecked", "error"]
    details: dict[str, str] = Field(default_factory=dict)
