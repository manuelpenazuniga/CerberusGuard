from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


EXECUTION_ID_RE = re.compile(r"Execution ID\s*\|\s*([0-9a-fA-F-]{36})")


@dataclass(frozen=True)
class ExecResult:
    command: str
    profile: str
    returncode: int
    stdout: str
    stderr: str
    execution_id: str | None


class CerberusClient:
    def __init__(self, *, agent_id: str, gateway_url: str = "http://localhost:8080/v1") -> None:
        self.agent_id = agent_id
        self.gateway_url = gateway_url.rstrip("/")
        self.correlation_id = str(uuid4())

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        declared_intent: str | None = None,
        declared_paths: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": kwargs.pop("model", "gemma4:e4b"),
            "messages": messages,
            "stream": kwargs.pop("stream", False),
            **kwargs,
        }
        payload["_lobstertrap"] = {
            "agent_id": self.agent_id,
            "correlation_id": self.correlation_id,
            "declared_intent": declared_intent,
            "declared_paths": declared_paths or [],
        }
        headers = {"Content-Type": "application/json", "X-Correlation-Id": self.correlation_id}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.gateway_url}/chat/completions", headers=headers, json=payload)
            try:
                data = response.json()
            except ValueError:
                data = {"status_code": response.status_code, "text": response.text}
        return data

    def exec(self, command: str, *, profile: str = "safe") -> ExecResult:
        clawcrate_bin = os.environ.get(
            "CERBERUS_CLAWCRATE_BIN", "external/clawcrate/target/release/clawcrate"
        )
        args = [
            clawcrate_bin,
            "run",
            "--profile",
            profile,
            "--",
            *shlex.split(command),
        ]
        env = os.environ.copy()
        env["CG_CORRELATION_ID"] = self.correlation_id
        proc = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
        execution_id = parse_execution_id(proc.stdout)
        if execution_id:
            write_correlation_map(execution_id, self.correlation_id)
        return ExecResult(
            command=command,
            profile=profile,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            execution_id=execution_id,
        )


def parse_execution_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        match = EXECUTION_ID_RE.search(line)
        if match:
            return match.group(1)
    return None


def write_correlation_map(execution_id: str, correlation_id: str) -> None:
    map_path = Path(
        os.environ.get(
            "CERBERUS_CLAWCRATE_CORRELATION_MAP", str(Path.home() / ".clawcrate" / "correlation_map.json")
        )
    )
    map_path.parent.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    if map_path.exists():
        try:
            mapping = json.loads(map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mapping = {}
    mapping[execution_id] = correlation_id
    map_path.write_text(json.dumps(mapping), encoding="utf-8")
