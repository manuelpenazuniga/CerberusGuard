from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class AdapterConfig:
    log_path: Path
    collector_url: str
    follow: bool


def parse_args(argv: list[str] | None = None) -> AdapterConfig:
    parser = argparse.ArgumentParser(
        prog="python -m cerberusguard.adapters.lobstertrap",
        description="Tail Lobster Trap NDJSON log and forward TrustEvents to Cerberus collector.",
    )
    parser.add_argument("log_path", type=Path, help="Path to Lobster Trap NDJSON audit log.")
    parser.add_argument(
        "--collector",
        default=os.environ.get("CERBERUS_COLLECTOR_URL", "http://127.0.0.1:9090"),
        help="Collector base URL (default: http://127.0.0.1:9090).",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Read file once and exit (do not tail).",
    )
    args = parser.parse_args(argv)
    return AdapterConfig(
        log_path=args.log_path,
        collector_url=args.collector.rstrip("/"),
        follow=not args.no_follow,
    )


def default_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_verdict(raw: str | None) -> str:
    if not raw:
        return "LOG"
    value = raw.strip().upper().replace("-", "_")
    mapping = {
        "ALLOW": "ALLOW",
        "DENY": "DENY",
        "BLOCK": "DENY",
        "HUMAN_REVIEW": "HUMAN_REVIEW",
        "RATE_LIMIT": "RATE_LIMIT",
        "QUARANTINE": "QUARANTINE",
        "LOG": "LOG",
    }
    return mapping.get(value, "LOG")


_VERDICT_TOKENS = {"ALLOW", "DENY", "LOG", "HUMAN_REVIEW", "RATE_LIMIT", "QUARANTINE", "BLOCK"}


def _split_verdict_and_action(raw: dict[str, Any]) -> tuple[str, str]:
    """Lobster Trap audit events carry the verdict in the `action` field
    (uppercase ALLOW/DENY/...) and the matched policy rule in `rule_name`.
    Some forks or future versions may emit a separate `verdict` field. Handle
    both shapes; never silently downgrade a real DENY to a LOG."""
    verdict_field = raw.get("verdict")
    action_field = raw.get("action")
    if isinstance(verdict_field, str):
        return verdict_field, str(
            raw.get("rule_name") or raw.get("matched_rule") or action_field or "log_observed"
        )
    if isinstance(action_field, str) and action_field.upper() in _VERDICT_TOKENS:
        return action_field, str(raw.get("rule_name") or raw.get("matched_rule") or "default")
    return "LOG", str(action_field or raw.get("event_type") or "log_observed")


def map_lobstertrap_event(raw: dict[str, Any]) -> dict[str, Any]:
    forced_correlation_id = os.environ.get("CERBERUS_CORRELATION_ID")
    payload = {
        k: v
        for k, v in raw.items()
        if k
        not in {
            "timestamp",
            "agent_id",
            "request_id",
            "correlation_id",
            "verdict",
            "action",
        }
    }
    correlation_id = str(
        forced_correlation_id
        or raw.get("correlation_id")
        or raw.get("session_id")
        or raw.get("request_id")
        or f"lt-{int(time.time() * 1000)}"
    )
    verdict_raw, action_label = _split_verdict_and_action(raw)
    event: dict[str, Any] = {
        "timestamp": str(raw.get("timestamp") or default_timestamp()),
        "agent_id": str(raw.get("agent_id") or raw.get("agent") or "lobstertrap-adapter"),
        "request_id": (
            str(raw.get("request_id")) if raw.get("request_id") is not None else None
        ),
        "correlation_id": correlation_id,
        "layer": "lobster_trap",
        "verdict": normalize_verdict(verdict_raw),
        "action": action_label,
        "payload": payload,
    }
    return event


def read_ndjson(path: Path, follow: bool) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        while True:
            line = fh.readline()
            if not line:
                if follow:
                    time.sleep(0.25)
                    continue
                return
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as err:
                print(f"[lobstertrap-adapter] invalid json line: {err}", file=sys.stderr)
                continue
            if not isinstance(record, dict):
                print("[lobstertrap-adapter] ignored non-object json line", file=sys.stderr)
                continue
            yield record


def post_event(client: httpx.Client, collector_url: str, event: dict[str, Any]) -> None:
    try:
        response = client.post(f"{collector_url}/events", json=event, timeout=2.0)
        if response.status_code >= 400:
            print(
                f"[lobstertrap-adapter] collector returned {response.status_code}: {response.text}",
                file=sys.stderr,
            )
    except Exception as err:  # fail-open: log and continue
        print(f"[lobstertrap-adapter] collector unreachable: {err}", file=sys.stderr)


def wait_for_log(log_path: Path, *, timeout_seconds: float = 120.0) -> bool:
    """Wait for the audit log to appear. Lobster Trap creates the file lazily
    on its first request, so an adapter started by an orchestrator may race
    ahead of the proxy. We poll instead of failing immediately."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if log_path.exists():
            return True
        time.sleep(0.5)
    return False


def run(config: AdapterConfig) -> int:
    if not config.log_path.exists():
        print(
            f"[lobstertrap-adapter] waiting for {config.log_path} (created lazily by LT)...",
            file=sys.stderr,
        )
        if not wait_for_log(config.log_path):
            print(
                f"[lobstertrap-adapter] timed out waiting for {config.log_path}",
                file=sys.stderr,
            )
            return 1
    with httpx.Client() as client:
        for raw_event in read_ndjson(config.log_path, follow=config.follow):
            mapped = map_lobstertrap_event(raw_event)
            post_event(client, config.collector_url, mapped)
    return 0


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
