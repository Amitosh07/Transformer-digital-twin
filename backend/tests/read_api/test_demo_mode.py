import pytest

from app.core.config import get_settings
from app.services.demo_mode import is_demo_mode


@pytest.mark.parametrize(
    "source,scenario,expected",
    [
        (None, None, False),
        ("plant-sensor", None, False),
        ("replay-public-data", None, True),
        ("SIMULATOR-NORMAL", None, True),
        ("mqtt-simulator", None, True),
        ("analytics-backfill", None, True),
        ("seed", None, True),
        ("demo", None, True),
        ("plant-sensor", "scenario", True),
        (None, "", True),
    ],
)
def test_demo_rule(source: str | None, scenario: str | None, expected: bool) -> None:
    assert is_demo_mode(source, scenario) is expected


def test_configurable_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_SOURCE_NAMES", "historical, test, ")
    get_settings.cache_clear()
    assert is_demo_mode("HISTORICAL-2020", None)
    assert not is_demo_mode("replay", None)
