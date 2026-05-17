#!/usr/bin/env bash
set -euo pipefail

HOSTS_FILE="${HOSTS_FILE:-/etc/hosts}"
TARGET_DOMAIN="${TARGET_DOMAIN:-evil.example.com}"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
HONEYPOT_PORT="${HONEYPOT_PORT:-8443}"
HONEYPOT_HOST="${HONEYPOT_HOST:-127.0.0.1}"
PID_FILE="${PID_FILE:-/private/tmp/cerberus-honeypot.pid}"

LINE="$TARGET_IP $TARGET_DOMAIN"

echo "[setup] ensuring hosts entry: $LINE"
if grep -qE "^[[:space:]]*$TARGET_IP[[:space:]]+$TARGET_DOMAIN([[:space:]]|$)" "$HOSTS_FILE"; then
  echo "[setup] hosts entry already present"
else
  if [[ "$HOSTS_FILE" == "/etc/hosts" ]]; then
    echo "[setup] adding hosts entry (sudo required)"
    echo "$LINE" | sudo tee -a "$HOSTS_FILE" >/dev/null
  else
    echo "[setup] adding hosts entry to $HOSTS_FILE"
    echo "$LINE" >>"$HOSTS_FILE"
  fi
  echo "[setup] hosts entry added"
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[setup] honeypot already running with pid $(cat "$PID_FILE")"
else
  echo "[setup] starting honeypot on $HONEYPOT_HOST:$HONEYPOT_PORT"
  nohup python3 demo/honeypot.py --host "$HONEYPOT_HOST" --port "$HONEYPOT_PORT" >/private/tmp/cerberus-honeypot.log 2>&1 &
  PID=$!
  echo "$PID" >"$PID_FILE"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    echo "[setup] honeypot pid $PID"
  else
    echo "[setup] honeypot failed to stay alive, check /private/tmp/cerberus-honeypot.log" >&2
    exit 1
  fi
fi

echo "[setup] verify with:"
echo "  curl http://$TARGET_DOMAIN:$HONEYPOT_PORT/"
echo "[setup] cleanup with:"
echo "  ./demo/honeypot-cleanup.sh"
