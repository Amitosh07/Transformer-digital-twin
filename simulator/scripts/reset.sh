#!/usr/bin/env bash
# reset.sh — Reset the demo to a clean state.
# simulator_README §15
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
TOKEN="${DEMO_ADMIN_TOKEN:-}"

echo "=== Resetting demo state ==="
python -m simulator.cli reset \
    --http-url "${BACKEND_URL}" \
    --token "${TOKEN}" \
    --yes

echo "=== Reset complete ==="
