#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY_TMP="$(mktemp -d)"
trap 'rm -rf "$VERIFY_TMP"' EXIT

echo "[1/5] Go backend tests"
(cd "$PROJECT_DIR/backend" && GOCACHE="$VERIFY_TMP/go-build" go test ./...)

echo "[2/5] Python solver lint"
if [[ -x "$PROJECT_DIR/solver/.venv/bin/ruff" ]]; then
  (cd "$PROJECT_DIR/solver" && .venv/bin/ruff check src tests)
else
  (cd "$PROJECT_DIR/solver" && python3 -m ruff check src tests)
fi

echo "[3/5] Python solver tests"
if [[ -x "$PROJECT_DIR/solver/.venv/bin/python" ]]; then
  "$PROJECT_DIR/solver/.venv/bin/python" -m pytest "$PROJECT_DIR/solver/tests"
else
  python3 -m pytest "$PROJECT_DIR/solver/tests"
fi

echo "[4/5] Frontend tests and typecheck"
(cd "$PROJECT_DIR/frontend" && npm test && npm run typecheck)

echo "[5/5] Production frontend build"
(cd "$PROJECT_DIR/frontend" && npm run build)

echo "All local verification checks passed."
