"""Delete demo data in one transaction; explicit --yes and non-production required."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.demo_service import require_demo_environment, reset_demo


def run_reset(
    *, yes: bool, include_transformers: bool = False, base_url: str | None = None
) -> dict[str, int]:
    settings = get_settings()
    require_demo_environment(settings)
    if not yes:
        raise ValueError("Demo reset requires --yes")
    if base_url:
        token = os.getenv("DEMO_ADMIN_TOKEN")
        if token is None:
            token = (
                settings.demo_admin_token.get_secret_value() if settings.demo_admin_token else ""
            )
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as client:
            response = client.post(
                "/api/v1/admin/demo/reset",
                headers={"X-Admin-Token": token},
                params={"include_transformers": include_transformers},
            )
            response.raise_for_status()
            return response.json()["deleted"]
    with SessionLocal() as session:
        return reset_demo(
            session, settings, yes=True, include_transformers=include_transformers
        ).deleted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--include-transformers", action="store_true")
    parser.add_argument("--base-url")
    args = parser.parse_args()
    try:
        print(json.dumps(run_reset(**vars(args)), indent=2))
    except (ValueError, httpx.HTTPError) as exc:
        parser.exit(
            1,
            f"Reset failed: {type(exc).__name__}: check --yes and admin configuration\n",
        )


if __name__ == "__main__":
    main()
