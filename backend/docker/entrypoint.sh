#!/bin/sh
set -eu
python scripts/wait_for_db.py
python -m alembic upgrade head
exec "$@"
