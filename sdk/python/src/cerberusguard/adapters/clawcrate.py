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
    runs_root: Path
    collector_url: str
    follow: bool
    correlation_map: Path


def parse_args(argv: list[str] | None = None) -> AdapterConfig:
    parser = argparse.ArgumentParser(
        prog="python -m cerberusguard.adapters.clawcrate",
        description="Watch ClawCrate audit.ndjson files and forward TrustEvents to Cerberus collector.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path.home() / ".clawcrate" / "runs",
        help="Root directory containing ClawCrate run directories.",
    )
    parser.add_argument(
        "--collector",
        default=os.environ.get("CERBERUS_COLLECTOR_URL", "http://127.0.0.1:9090"),
        help="Collector base URL (default: http://127.0.0.1:9090).",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Process current files once and exit.",
    )
    args = parser.parse_args(argv)
    return AdapterConfig(
        runs_root=args.runs_root,
        collector_url=args.collector.rstrip("/"),
        follow=not args.no_follow,
        correlation_map=Path(
            os.environ.get(
                "CERBERUS_CLAWCRATE_CORRELATION_MAP",
                str(Path.home() / ".clawcrate" / "correlation_map.json"),
            )
        ),
    )


def default_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def event_name(raw: dict[str, Any]) -> str:
    event = raw.get("event")
    if isinstance(event, dict) and event:
        return next(iter(event.keys()))
    return "Unknown"


def verdict_from_event(name: str, payload: dict[str, Any]) -> str:
    if name == "ProcessExited":
        exit_code = payload.get("exit_code")
        if isinstance(exit_code, int):
            return "ALLOW" if exit_code == 0 else "DENY"
    return "LOG"


def map_clawcrate_event(raw: dict[str, Any], run_id: str, correlation_id: str) -> dict[str, Any]:
    name = event_name(raw)
    payload_obj = {}
    event = raw.get("event")
    if isinstance(event, dict):
        payload_obj = event.get(name) if isinstance(event.get(name), dict) else {}
    event_payload = {
        "event_name": name,
        "details": payload_obj,
    }
    return {
        "timestamp": str(raw.get("timestamp") or default_timestamp()),
        "agent_id": "clawcrate-adapter",
        "request_id": None,
        "correlation_id": correlation_id,
        "layer": "claw_crate",
        "verdict": verdict_from_event(name, payload_obj),
        "action": name,
        "payload": event_payload,
    }


def post_event(client: httpx.Client, collector_url: str, event: dict[str, Any]) -> None:
    try:
        response = client.post(f"{collector_url}/events", json=event, timeout=2.0)
        if response.status_code >= 400:
            print(
                f"[clawcrate-adapter] collector returned {response.status_code}: {response.text}",
                file=sys.stderr,
            )
    except Exception as err:
        print(f"[clawcrate-adapter] collector unreachable: {err}", file=sys.stderr)


def iter_audit_files(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    audits = list(runs_root.glob("*/audit.ndjson"))
    audits.sort(key=lambda p: p.stat().st_mtime)
    return audits


def process_audit_file(path: Path, client: httpx.Client, collector_url: str) -> None:
    run_id = path.parent.name
    correlation_id = resolve_correlation_id(run_id)
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as err:
                print(f"[clawcrate-adapter] invalid json line in {path}: {err}", file=sys.stderr)
                continue
            if not isinstance(raw, dict):
                continue
            mapped = map_clawcrate_event(raw, run_id=run_id, correlation_id=correlation_id)
            post_event(client, collector_url, mapped)


def run(config: AdapterConfig) -> int:
    seen: set[Path] = set()
    global _CORRELATION_MAP_PATH
    _CORRELATION_MAP_PATH = config.correlation_map
    with httpx.Client() as client:
        while True:
            for path in iter_audit_files(config.runs_root):
                if path in seen:
                    continue
                process_audit_file(path, client, config.collector_url)
                seen.add(path)
            if not config.follow:
                return 0
            time.sleep(0.5)


_CORRELATION_MAP_PATH = Path.home() / ".clawcrate" / "correlation_map.json"


def resolve_correlation_id(run_id: str) -> str:
    path = _CORRELATION_MAP_PATH
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            mapped = data.get(run_id)
            if isinstance(mapped, str) and mapped:
                return mapped
        except json.JSONDecodeError:
            return run_id
    return run_id


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
