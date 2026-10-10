#!/usr/bin/env bash
# demo.sh — Run all 5 demo scenarios end-to-end.
# simulator_README §14
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
TRANSFORMER_ID="${TRANSFORMER_ID:-TX-001}"

echo "=============================================="
echo "  TRANSFORMER DIGITAL TWIN — DEMO"
echo "=============================================="
echo ""
echo "Step 1: Reset demo state"
python -m simulator.cli reset --http-url "${BACKEND_URL}" --yes 2>/dev/null || true
echo ""

echo "Step 2: Seed 24h of baseline data"
python -m simulator.cli seed --http-url "${BACKEND_URL}" --count 1440 --transformer-id "${TRANSFORMER_ID}"
echo ""

echo "Step 3: Run demo scenarios"
python -m simulator.cli demo --http-url "${BACKEND_URL}" --transformer-id "${TRANSFORMER_ID}" --records-per-scenario 10
echo ""

echo "=============================================="
echo "  DEMO COMPLETE — Check the dashboard"
echo "=============================================="
