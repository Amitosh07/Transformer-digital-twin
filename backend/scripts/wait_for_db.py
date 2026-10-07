"""Bounded database startup wait used by the container entrypoint."""

import sys
from pathlib import Path
from time import monotonic, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine


def main() -> None:
    deadline = monotonic() + 60
    while monotonic() < deadline:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except SQLAlchemyError:
            sleep(1)
    raise SystemExit("Database was not ready within 60 seconds")


if __name__ == "__main__":
    main()
