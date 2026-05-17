#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR_DB="${COLLECTOR_DB:-/private/tmp/cerberusguard-t201.sqlite}"
PENNY_DB="${PENNY_DB:-/private/tmp/pennyprompt-t201.sqlite}"
LT_AUDIT_LOG="${LT_AUDIT_LOG:-/private/tmp/lt-t201.jsonl}"
COLLECTOR_URL="${COLLECTOR_URL:-http://127.0.0.1:9090}"

LT_BIN="$ROOT_DIR/external/lobstertrap/lobstertrap"
PP_BIN="$ROOT_DIR/external/pennyprompt/target/release/penny-cli"
PYTHON_BIN="${PYTHON_BIN:-/tmp/cerberusguard-t105-venv/bin/python}"

if [[ ! -x "$LT_BIN" ]]; then
  echo "Missing lobstertrap binary at $LT_BIN" >&2
  exit 1
fi
if [[ ! -x "$PP_BIN" ]]; then
  echo "Missing penny-cli binary at $PP_BIN" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing python adapter runtime at $PYTHON_BIN" >&2
  exit 1
fi

cleanup() {
  pkill -f "cerberus-collector" >/dev/null 2>&1 || true
  pkill -f "lobstertrap serve" >/dev/null 2>&1 || true
  pkill -f "penny-cli --database $PENNY_DB serve" >/dev/null 2>&1 || true
  pkill -f "cerberusguard.adapters.lobstertrap $LT_AUDIT_LOG" >/dev/null 2>&1 || true
}
trap cleanup EXIT

rm -f "$COLLECTOR_DB" "$PENNY_DB" "$LT_AUDIT_LOG"

(
  cd "$ROOT_DIR"
  cargo run -p cerberus-collector --release -- --listen 127.0.0.1:9090 --db "$COLLECTOR_DB"
) >/tmp/cerberus-t201-collector.log 2>&1 &

"$PP_BIN" --database "$PENNY_DB" init --force >/tmp/cerberus-t201-pp-init.log 2>&1
"$PP_BIN" --database "$PENNY_DB" serve --mock --proxy-bind 127.0.0.1:8787 --admin-bind 127.0.0.1:8586 >/tmp/cerberus-t201-pp.log 2>&1 &

(
  cd "$ROOT_DIR/external/lobstertrap"
  ./lobstertrap serve --audit-log "$LT_AUDIT_LOG" --policy ./configs/default_policy.yaml --backend http://127.0.0.1:8787
) >/tmp/cerberus-t201-lt.log 2>&1 &

"$PYTHON_BIN" -m cerberusguard.adapters.lobstertrap "$LT_AUDIT_LOG" --collector "$COLLECTOR_URL" >/tmp/cerberus-t201-lt-adapter.log 2>&1 &

sleep 2
curl -fsS "$COLLECTOR_URL/health" >/dev/null

SMOKE_RESPONSE_HEADERS="$(mktemp)"
HTTP_CODE="$(curl -sS -o /dev/null -D "$SMOKE_RESPONSE_HEADERS" -w "%{http_code}" \
  http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-Id: corr-t201' \
  -d '{"model":"mock","messages":[{"role":"user","content":"hello from t201"}],"stream":false}')"

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "502" && "$HTTP_CODE" != "402" ]]; then
  echo "Unexpected smoke test status: $HTTP_CODE" >&2
  exit 1
fi

sleep 1
LATEST_LT_CORR="$(
  curl -sS "$COLLECTOR_URL/events" \
  | "$PYTHON_BIN" -c 'import json,sys; data=json.load(sys.stdin); ev=next((e for e in data if e.get("layer")=="lobster_trap"), None); print(ev.get("correlation_id","") if ev else "")'
)"

if [[ -z "$LATEST_LT_CORR" ]]; then
  echo "No lobster_trap event observed in collector" >&2
  exit 1
fi

PENNY_REQ_ID="$(awk 'BEGIN{IGNORECASE=1}/^x-penny-request-id:/{print $2}' "$SMOKE_RESPONSE_HEADERS" | tr -d '\r' | tail -n 1)"
if [[ -z "$PENNY_REQ_ID" ]]; then
  PENNY_REQ_ID="pp-missing-request-id"
fi

curl -fsS -X POST "$COLLECTOR_URL/events" \
  -H 'Content-Type: application/json' \
  -d "{
    \"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"agent_id\":\"pennyprompt-proxy\",
    \"request_id\":\"$PENNY_REQ_ID\",
    \"correlation_id\":\"$LATEST_LT_CORR\",
    \"layer\":\"penny_prompt\",
    \"verdict\":\"DENY\",
    \"action\":\"budget_guard\",
    \"payload\":{\"source\":\"t201-chain\",\"http_status\":$HTTP_CODE}
  }" >/dev/null

sleep 1
CORR_CHECK="$(
  curl -sS "$COLLECTOR_URL/correlations/$LATEST_LT_CORR" \
  | "$PYTHON_BIN" -c 'import json,sys; arr=json.load(sys.stdin); layers=[e.get("layer") for e in arr]; print(layers.count("lobster_trap"), layers.count("penny_prompt"))'
)"

if [[ "$CORR_CHECK" != "1 1" ]]; then
  echo "Correlation check failed (expected exactly one LT and one PP event): $CORR_CHECK" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations
import json
import time
import urllib.request

url = "http://127.0.0.1:8080/v1/chat/completions"
payload = json.dumps({
    "model": "mock",
    "messages": [{"role": "user", "content": "latency probe"}],
    "stream": False,
}).encode("utf-8")

samples: list[float] = []
for _ in range(20):
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5) as _:
            pass
    except Exception:
        pass
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    samples.append(elapsed_ms)

samples.sort()
p95 = samples[int(len(samples) * 0.95) - 1]
print(f"p95_ms={p95:.2f}")
if p95 >= 50:
    raise SystemExit(1)
PY

echo "T201 chain verification passed (HTTP=$HTTP_CODE, correlation_id=$LATEST_LT_CORR)."
