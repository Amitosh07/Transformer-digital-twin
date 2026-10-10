"""Deliberately regenerate the reviewed OpenAPI compatibility baseline."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "tests" / "snapshots" / "openapi.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(path)


if __name__ == "__main__":
    main()
