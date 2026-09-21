#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
SMOKE_TMP="$(mktemp -d)"
CREATED_REQUEST_ID=""
SMOKE_EXTERNAL_ID="deployment-smoke-request-$(date +%s)-$$"

cleanup() {
  if [[ -n "$CREATED_REQUEST_ID" ]]; then
    curl -fsS -X DELETE "$BASE_URL/api/v1/requests/$CREATED_REQUEST_ID" >/dev/null 2>&1 || true
  fi
  rm -rf "$SMOKE_TMP"
}
trap cleanup EXIT

echo "[1/5] Health and database connectivity"
curl -fsS "$BASE_URL/healthz" >"$SMOKE_TMP/health.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1])) == {"status":"ok"}' "$SMOKE_TMP/health.json"

echo "[2/5] React application is served"
curl -fsS "$BASE_URL/" >"$SMOKE_TMP/index.html"
grep -q 'id="root"' "$SMOKE_TMP/index.html"

echo "[3/5] OpenAPI contract includes delete endpoints"
curl -fsS "$BASE_URL/swagger/doc.json" >"$SMOKE_TMP/swagger.json"
python3 -c 'import json,sys; p=json.load(open(sys.argv[1]))["paths"]; assert "delete" in p["/requests/"]; assert "delete" in p["/requests/{id}"]' "$SMOKE_TMP/swagger.json"

echo "[4/5] Request create/list lifecycle"
curl -fsS -X POST "$BASE_URL/api/v1/requests/" \
  -H 'Content-Type: application/json' \
  -d "{\"external_id\":\"$SMOKE_EXTERNAL_ID\",\"address\":\"Smoke test point\",\"latitude\":55.7558,\"longitude\":37.6176,\"service_minutes\":10,\"window_start\":\"10:00\",\"window_end\":\"12:00\",\"required_skill\":\"local\",\"priority\":\"normal\"}" \
  >"$SMOKE_TMP/request.json"
CREATED_REQUEST_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$SMOKE_TMP/request.json")"
curl -fsS "$BASE_URL/api/v1/requests/$CREATED_REQUEST_ID" >"$SMOKE_TMP/request-get.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["id"] == sys.argv[2]' "$SMOKE_TMP/request-get.json" "$CREATED_REQUEST_ID"

echo "[5/5] Request delete lifecycle"
curl -fsS -X DELETE "$BASE_URL/api/v1/requests/$CREATED_REQUEST_ID" >/dev/null
STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/requests/$CREATED_REQUEST_ID")"
[[ "$STATUS" == "404" ]]
CREATED_REQUEST_ID=""

echo "Deployment smoke test passed."
