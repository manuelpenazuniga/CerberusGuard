#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR_DB="${COLLECTOR_DB:-/private/tmp/cerberusguard-demo.sqlite}"
PENNY_DB="${PENNY_DB:-/private/tmp/pennyprompt-demo.sqlite}"
LT_AUDIT_LOG="${LT_AUDIT_LOG:-/private/tmp/lt-demo.jsonl}"
PP_AUDIT_LOG="${PP_AUDIT_LOG:-/private/tmp/pp-demo.ndjson}"
COLLECTOR_URL="${COLLECTOR_URL:-http://127.0.0.1:9090}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8080/v1}"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:3000}"
PYTHON_BIN="${PYTHON_BIN:-/tmp/cerberusguard-t105-venv/bin/python}"

LT_BIN="$ROOT_DIR/external/lobstertrap/lobstertrap"
PP_BIN="$ROOT_DIR/external/pennyprompt/target/release/penny-cli"

cleanup() {
  jobs -p | xargs -r kill || true
}
trap cleanup EXIT

echo "[demo] building Rust workspace"
(
  cd "$ROOT_DIR"
  cargo build --workspace --release
)

echo "[demo] installing dashboard dependencies"
(
  cd "$ROOT_DIR/dashboard"
  npm install >/dev/null
)

echo "[demo] compiling policy"
(
  cd "$ROOT_DIR"
  cargo run -p cerberus-policy -- compile policy/examples/healthcare-strict.yaml --out-dir /private/tmp/compiled-demo
)

rm -f "$COLLECTOR_DB" "$PENNY_DB" "$LT_AUDIT_LOG" "$PP_AUDIT_LOG"

# ---------------------------------------------------------------------------
# Boot order matters. Adapters fail-open but the demo "looks broken" on the
# dashboard if they spend the first 30 s reporting "connection refused" to a
# collector that is still compiling. So:
#   1. Start the collector first, then poll /health until it answers.
#   2. Start PP and LT (they themselves will boot in parallel).
#   3. Only then start adapters; their audit-log inputs are also lazily
#      created — the adapters now wait_for_log() instead of exiting fast.
# ---------------------------------------------------------------------------

echo "[demo] starting collector"
(
  cd "$ROOT_DIR"
  cargo run -p cerberus-collector --release -- --listen 127.0.0.1:9090 --db "$COLLECTOR_DB"
) >/private/tmp/cerberus-demo-collector.log 2>&1 &

echo "[demo] waiting for collector /health"
for i in $(seq 1 60); do
  if curl -fsS "$COLLECTOR_URL/health" >/dev/null 2>&1; then
    echo "[demo] collector ready after ${i}s"
    break
  fi
  if [[ "$i" -eq 60 ]]; then
    echo "[demo] collector did not become healthy within 60s — aborting" >&2
    exit 1
  fi
  sleep 1
done

echo "[demo] starting PennyPrompt"
"$PP_BIN" --database "$PENNY_DB" init --force >/private/tmp/cerberus-demo-pp-init.log 2>&1
# stderr separated so it does not contaminate the NDJSON the adapter tails.
"$PP_BIN" --database "$PENNY_DB" serve --mock --proxy-bind 127.0.0.1:8787 --admin-bind 127.0.0.1:8586 --json-log \
  >"$PP_AUDIT_LOG" 2>/private/tmp/cerberus-demo-pp.err.log &

echo "[demo] starting Lobster Trap"
(
  cd "$ROOT_DIR/external/lobstertrap"
  ./lobstertrap serve --audit-log "$LT_AUDIT_LOG" --policy ./configs/default_policy.yaml --backend http://127.0.0.1:8787
) >/private/tmp/cerberus-demo-lt.log 2>&1 &

echo "[demo] starting adapters (they wait for their audit logs to appear)"
CERBERUS_CORRELATION_ID=corr-demo "$PYTHON_BIN" -m cerberusguard.adapters.lobstertrap "$LT_AUDIT_LOG" --collector "$COLLECTOR_URL" >/private/tmp/cerberus-demo-lt-adapter.log 2>&1 &
CERBERUS_CORRELATION_ID=corr-demo "$PYTHON_BIN" -m cerberusguard.adapters.pennyprompt "$PP_AUDIT_LOG" --collector "$COLLECTOR_URL" >/private/tmp/cerberus-demo-pp-adapter.log 2>&1 &
"$PYTHON_BIN" -m cerberusguard.adapters.clawcrate --collector "$COLLECTOR_URL" >/private/tmp/cerberus-demo-cc-adapter.log 2>&1 &

echo "[demo] starting dashboard"
(
  cd "$ROOT_DIR/dashboard"
  npm run dev
) >/private/tmp/cerberus-demo-dashboard.log 2>&1 &

echo "[demo] waiting for LT and PP to bind (5 s)"
sleep 5

echo "Dashboard ready at $DASHBOARD_URL"
read -r -p "Press ENTER to run unprotected scenario..."

echo "[demo] running unprotected malicious-agent flow"
"$PYTHON_BIN" "$ROOT_DIR/demo/run-malicious-agent.py" --mode unprotected

read -r -p "Press ENTER to run protected scenario..."

echo "[demo] running protected malicious-agent flow"
CERBERUS_COLLECTOR_URL="$COLLECTOR_URL" "$PYTHON_BIN" "$ROOT_DIR/demo/run-malicious-agent.py" --mode protected --gateway-url "$GATEWAY_URL" --collector-url "$COLLECTOR_URL" --correlation-id corr-demo

read -r -p "Press ENTER to stop all demo services..."
echo "[demo] cleanup complete"
