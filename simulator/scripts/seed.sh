#!/usr/bin/env bash
# seed.sh — Bulk-seed the backend with 24 hours of normal synthetic data.
# simulator_README §12
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
COUNT="${1:-1440}"
TRANSFORMER_ID="${TRANSFORMER_ID:-TX-001}"

echo "=== Seeding backend with ${COUNT} records ==="
python -m simulator.cli seed \
    --http-url "${BACKEND_URL}" \
    --count "${COUNT}" \
    --transformer-id "${TRANSFORMER_ID}" \
    --seed 42

echo "=== Seed complete ==="
