#!/usr/bin/env bash
set -euo pipefail

HOSTS_FILE="${HOSTS_FILE:-/etc/hosts}"
TARGET_DOMAIN="${TARGET_DOMAIN:-evil.example.com}"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
PID_FILE="${PID_FILE:-/private/tmp/cerberus-honeypot.pid}"

LINE_REGEX="^[[:space:]]*$TARGET_IP[[:space:]]+$TARGET_DOMAIN([[:space:]]|$)"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "[cleanup] stopping honeypot pid $PID"
    kill "$PID" || true
  fi
  rm -f "$PID_FILE"
fi

if grep -qE "$LINE_REGEX" "$HOSTS_FILE"; then
  echo "[cleanup] removing hosts entry for $TARGET_DOMAIN"
  TMP_FILE="$(mktemp)"
  grep -vE "$LINE_REGEX" "$HOSTS_FILE" >"$TMP_FILE"
  if [[ "$HOSTS_FILE" == "/etc/hosts" ]]; then
    sudo cp "$TMP_FILE" "$HOSTS_FILE"
  else
    cp "$TMP_FILE" "$HOSTS_FILE"
  fi
  rm -f "$TMP_FILE"
  echo "[cleanup] hosts entry removed"
else
  echo "[cleanup] hosts entry already absent"
fi
