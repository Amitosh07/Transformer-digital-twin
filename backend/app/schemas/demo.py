"""Administrative demo reset response; canonical models remain unchanged."""

from pydantic import BaseModel


class DemoResetOut(BaseModel):
    deleted: dict[str, int]
