from pydantic import ConfigDict, Field

from app.schemas.analytics import AnalyticsOut
from app.schemas.common import CanonicalModel
from app.schemas.query import DataSource
from app.schemas.telemetry import TelemetryOut
from app.schemas.transformer import TransformerOut
from app.schemas.hackathon import AnalyticsAvailability


class LatestStateOut(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)

    transformer: TransformerOut
    telemetry: TelemetryOut | None = None
    analytics: AnalyticsOut | None = None
    open_alerts_count: int = Field(ge=0)
    demo_mode: bool
    data_source: DataSource = Field(default_factory=DataSource)
    schema_version: str
    feature_version: str | None = None
    model_version: str | None = None
    analytics_availability: AnalyticsAvailability | None = None
