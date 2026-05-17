from __future__ import annotations

import argparse
import time
from typing import Any

import httpx

from cerberusguard import CerberusClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day-2 healthy session verification.")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--collector-url", default="http://127.0.0.1:9090")
    parser.add_argument("--agent-id", default="day2-test")
    parser.add_argument("--correlation-id", default="corr-t208")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args()


def fetch_correlation_events(collector_url: str, correlation_id: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=5.0) as client:
        response = client.get(f"{collector_url.rstrip('/')}/correlations/{correlation_id}")
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, list) else []


def main() -> int:
    args = parse_args()
    client = CerberusClient(agent_id=args.agent_id, gateway_url=args.gateway_url)
    client.correlation_id = args.correlation_id

    print(f"[t208] correlation_id={client.correlation_id}")
    print("[t208] chat()")
    client.chat(messages=[{"role": "user", "content": "Hello world"}], model="mock")
    print("[t208] exec('echo hi')")
    client.exec("echo hi", profile="safe")
    print("[t208] exec('ls /tmp')")
    client.exec("ls /tmp", profile="safe")

    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline:
        events = fetch_correlation_events(args.collector_url, client.correlation_id)
        layers = {event.get("layer") for event in events}
        if len(events) >= 3 and {"lobster_trap", "penny_prompt", "claw_crate"}.issubset(layers):
            print(f"[t208] ok events={len(events)} layers={sorted(layers)}")
            return 0
        time.sleep(1)

    events = fetch_correlation_events(args.collector_url, client.correlation_id)
    layers = {event.get("layer") for event in events}
    print(f"[t208] failed events={len(events)} layers={sorted(layers)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
