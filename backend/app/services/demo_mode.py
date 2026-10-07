"""One rule for marking replay, simulator and scenario data for dashboards."""

from app.core.config import get_settings


def is_demo_mode(source_name: str | None, scenario_id: str | None) -> bool:
    if scenario_id is not None:
        return True
    source = (source_name or "").casefold()
    prefixes = [
        name.strip().casefold()
        for name in get_settings().demo_source_names.split(",")
        if name.strip()
    ]
    return any(source.startswith(prefix) for prefix in prefixes)
