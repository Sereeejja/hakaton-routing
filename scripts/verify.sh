#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY_TMP="$(mktemp -d)"
trap 'rm -rf "$VERIFY_TMP"' EXIT

echo "[1/4] Go backend tests"
(cd "$PROJECT_DIR/backend" && GOCACHE="$VERIFY_TMP/go-build" go test ./...)

echo "[2/4] Python solver tests"
if [[ -x "$PROJECT_DIR/solver/.venv/bin/python" ]]; then
  "$PROJECT_DIR/solver/.venv/bin/python" -m pytest "$PROJECT_DIR/solver/tests"
else
  python3 -m pytest "$PROJECT_DIR/solver/tests"
fi

echo "[3/4] Frontend tests and typecheck"
(cd "$PROJECT_DIR/frontend" && npm test && npm run typecheck)

echo "[4/4] Production frontend build"
(cd "$PROJECT_DIR/frontend" && npm run build)

echo "All local verification checks passed."
