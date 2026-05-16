<div align="center">

# CerberusGuard

### Three heads. One guardian. Zero trust between layers.

**The defense-in-depth trust layer for production AI agents — built on three open-source primitives, deployable today.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-yellow.svg)]()
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS-blue.svg)]()
[![Rust](https://img.shields.io/badge/rust-1.80%2B-orange.svg)](https://www.rust-lang.org/)
[![Node](https://img.shields.io/badge/node-22%2B-brightgreen.svg)](https://nodejs.org/)
[![Built on Lobster Trap](https://img.shields.io/badge/built%20on-Lobster%20Trap-ff6f3c.svg)](https://github.com/veeainc/lobstertrap)
[![TechEx 2026 — Track 1](https://img.shields.io/badge/TechEx%202026-Track%201%20Agent%20Security-purple.svg)](https://lablab.ai/ai-hackathons/techex-intelligent-enterprise-solutions-hackathon)

</div>

---

```
                              ┌─────────────────┐
                              │      AGENT      │
                              └────────┬────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            │                          │                          │
            ▼                          ▼                          ▼
   ┌────────────────┐        ┌─────────────────┐         ┌────────────────┐
   │   HEAD ONE     │        │    HEAD TWO     │         │   HEAD THREE   │
   │ Prompt Inspect │        │ Budget Governor │         │  Exec Sandbox  │
   │  (Lobster Trap)│        │  (PennyPrompt)  │         │   (ClawCrate)  │
   └────────┬───────┘        └────────┬────────┘         └────────┬───────┘
            │                         │                           │
            └─────────────────────────┼───────────────────────────┘
                                      ▼
                          ┌───────────────────────┐
                          │  CerberusGuard Core   │
                          │  Unified audit log    │
                          │  Cross-layer policy   │
                          │  Real-time dashboard  │
                          │  SOC2 / ISO 27001 exp │
                          └───────────────────────┘
```

---

## Why CerberusGuard

Fortune 500 teams are shipping AI agents to production without the controls their security organisations would sign off on for any other workload. The standard stack has three open gaps, each of which is a documented attack surface:

| # | Gap                  | Documented attack                                              | OWASP LLM ref |
|---|----------------------|----------------------------------------------------------------|---------------|
| 1 | **Prompt layer**     | Indirect prompt injection from poisoned docs, web pages, tools | LLM01         |
| 2 | **Budget layer**     | Looping agents burning 5- to 6-figures of LLM spend overnight  | LLM10         |
| 3 | **Execution layer**  | `postinstall` scripts reading `~/.ssh/`, `~/.aws/credentials`  | LLM02 / LLM05 |

Three independent threat surfaces, three independent best-in-class open-source tools, and — until now — no unified way to deploy them as one product.

**CerberusGuard is the integration layer.** It does not replace its three heads; it makes them speak the same language, share a policy bundle, and emit a single correlated audit trail that an auditor can read.

---

## The three heads

| Head | Component | What it enforces | Where it sits |
|------|-----------|-------------------|----------------|
| ![1](https://img.shields.io/badge/HEAD-1-orange) | [**Lobster Trap**](https://github.com/veeainc/lobstertrap) by Veea | Regex-based deep prompt inspection — sub-millisecond, 21 metadata fields (intent, risk, PII, credentials, paths). | Reverse proxy in front of the LLM |
| ![2](https://img.shields.io/badge/HEAD-2-yellow) | **[PennyPrompt](https://github.com/manuelpenazuniga/PennyPrompt)** | Atomic, pre-execution LLM budget control + similarity-based loop detection + append-only cost ledger. Returns HTTP 402 on cap. | Reverse proxy downstream of Head 1 |
| ![3](https://img.shields.io/badge/HEAD-3-purple) | **[ClawCrate](https://github.com/manuelpenazuniga/ClawCrate)** | Single-binary kernel-level sandbox — Landlock + seccomp on Linux, Seatbelt on macOS. Filesystem isolation, env scrubbing, replica mode for `npm install`-class commands. | Wraps every `exec()` the agent emits |

All three are MIT-licensed, all three work standalone, and all three already exist. CerberusGuard adds:

- **Unified `TrustEvent` schema** so the three heads correlate by `agent_id` + `correlation_id` instead of three disjoint log formats
- **Policy bundle compiler** — one YAML in, three configs out (Lobster Trap YAML, PennyPrompt TOML, ClawCrate YAML), so the source of truth never drifts
- **Real-time dashboard** with per-session timelines spanning all three heads
- **Audit export** in formats your compliance team already knows (SOC2-aligned NDJSON, ISO 27001 CSV, EU AI Act schema)
- **SDKs** for Python and TypeScript agents (set one env var, get the whole stack)

---

## What gets blocked, where

Defense in depth means each layer catches what the layer above missed. CerberusGuard makes that observable.

| Attack scenario | First catch point | Evidence in audit |
|-----------------|-------------------|-------------------|
| Hidden prompt injection in a poisoned README the agent reads as context | **Head 1** — Lobster Trap matches `contains_injection_patterns + target_paths` before the prompt reaches the LLM | `verdict: DENY`, `risk_score: 0.91`, matched rule, redacted excerpt |
| Agent misinterprets ambiguous instructions and loops on the same prompt | **Head 2** — PennyPrompt sees similarity > 0.85 between 4 consecutive prompts and trips loop detection | `verdict: DENY`, `loop_detection.consecutive_similar_count: 4` |
| Same agent's budget cap reached mid-task | **Head 2** — PennyPrompt rejects the next call with HTTP 402 | `verdict: DENY`, `budget_state.session_spent_usd`, ledger entry |
| `npm install` triggers a `postinstall` script that reads `~/.aws/credentials` | **Head 3** — ClawCrate filesystem deny + env scrubbing block the read | `verdict: ALLOW` (npm install succeeded), `fs_decisions.denied_paths_accessed: 3`, `env_scrubbed: [AWS_SECRET_ACCESS_KEY, ...]` |
| Sophisticated agent does all of the above in one session | **CerberusGuard Core** — single timeline view, single `correlation_id`, exportable to your SIEM | One unified session record across all three layers |

---

## Quickstart

### Prerequisites

| Tool       | Minimum | Used for                              |
|------------|---------|---------------------------------------|
| Rust       | 1.80+   | `cerberus-collector`, `cerberus-policy` CLI |
| Go         | 1.22+   | Building Lobster Trap (Head 1)        |
| Node.js    | 22+     | Dashboard                              |
| Python     | 3.10+   | Adapters and Python SDK               |
| Linux 5.13+ or macOS 12+ | — | ClawCrate (kernel sandbox)   |

### One-command demo

```bash
git clone https://github.com/manuelpenazuniga/CerberusGuard.git
cd CerberusGuard
./demo/run-demo.sh
```

The script:
1. Builds CerberusGuard, Lobster Trap, PennyPrompt, and ClawCrate (≈ 3 min cold, < 10 s warm)
2. Brings up the chain — `agent → LT (:8080) → PP (:8787) → Ollama (:11434)`
3. Starts the Core collector (`:9090`) and the dashboard (`:3000`)
4. Runs the **Poisoned Repo** attack scenario against an unprotected agent, then against a CerberusGuard-protected one
5. Opens the dashboard so you can see the attacks being blocked live

Total run time: about 90 seconds. Visit [http://localhost:3000](http://localhost:3000) for the dashboard.

### Use it in your own agent

Drop-in for any agent that speaks the OpenAI Chat Completions API. Set one base URL:

```bash
export OPENAI_BASE_URL="http://localhost:8080/v1"   # points at Head 1
```

Or use the Python SDK for correlation_id propagation and the ClawCrate wrapper in one place:

```python
from cerberusguard import CerberusClient

cg = CerberusClient(agent_id="my-coding-agent")

# LLM calls flow: SDK → Lobster Trap → PennyPrompt → LLM backend.
reply = cg.chat(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Refactor this function..."}],
    declared_intent="code_modification",
    declared_paths=["./src/"],
)

# Shell execution flows: SDK → ClawCrate → kernel sandbox, same correlation_id.
result = cg.exec("npm install", profile="install")
```

The same `correlation_id` ties the LLM call and the shell exec together in the dashboard and the audit export.

### Compile a unified policy

```bash
# One YAML, three configs — atomically distributed to all three heads.
cerberus-policy compile policy/examples/healthcare-strict.yaml --out-dir ./compiled/
# -> compiled/lobstertrap.yaml
# -> compiled/pennyprompt.toml
# -> compiled/clawcrate.yaml
```

This is the single most differentiated piece of CerberusGuard: no competitor distributes cross-layer policy from one source of truth.

---

## Architecture

### Two paths, three heads

```
                                    HTTP path (LLM calls)
                                    ─────────────────────
   ┌────────┐       ┌──────────────┐       ┌──────────────┐       ┌──────────┐
   │ Agent  │──────▶│  Lobster Trap│──────▶│  PennyPrompt │──────▶│   LLM    │
   └────┬───┘       │  (Head 1)    │       │  (Head 2)    │       │  Backend │
        │           │  :8080       │       │  :8787       │       └──────────┘
        │           └──────┬───────┘       └──────┬───────┘
        │                  │                      │
        │                  │  audit (ndjson)      │ audit (ndjson)
        │                  ▼                      ▼
        │           ┌──────────────────────────────────┐
        │           │  CerberusGuard Core (:9090)      │
        │           │    Unified event store           │
        │           │    Correlation by agent_id +     │
        │           │    correlation_id                │
        │           └──────────────┬───────────────────┘
        │                          ▲
        │           audit (ndjson) │
        │                          │
        │                  ┌───────┴──────┐
        └─────────────────▶│  ClawCrate   │   exec path (shell commands)
              exec(cmd)    │  (Head 3)    │   ────────────────────────
                           │  kernel-LSM  │
                           └──────────────┘

                          Dashboard (:3000) reads from Core for live & historical view.
```

**Why this order**

- **Head 1 first** — regex DPI is sub-millisecond. There is no reason to pay an LLM token to refuse a malicious prompt the proxy can deny for free in 2 ms.
- **Head 2 second** — budget enforcement requires an estimate that depends on the request being allowed to proceed.
- **Head 3 parallel** — shell execution is a different attack surface, not a stage of the LLM call.

### Unified event schema

Every event from every head serialises to the same shape:

```json
{
  "timestamp": "2026-05-15T14:32:11.234Z",
  "agent_id": "claude-code-prod-v2",
  "request_id": "req-7f3a9b",
  "correlation_id": "session-abc123",
  "layer": "lobster_trap",
  "verdict": "DENY",
  "action": "block_credential_exfiltration",
  "payload": {
    "risk_score": 0.91,
    "detected": {
      "contains_credentials": true,
      "contains_injection_patterns": true,
      "target_paths": ["/etc/shadow"]
    },
    "matched_rule": "rule_42_credential_exfil"
  }
}
```

The `correlation_id` is the join key. Given a session, the dashboard reconstructs the full timeline across all three heads.

### One YAML, three configs

```yaml
# policy/examples/healthcare-strict.yaml
version: "1.0"
policy_name: "healthcare-strict"
profile: "regulated"

agent_meta:
  budget_per_session_usd: 5.00
  budget_per_request_usd: 0.50
  max_session_duration_minutes: 30

prompt_inspection:           # → Head 1: Lobster Trap rules
  block:
    - prompt_injection
    - credential_exfiltration
    - phi_exposure
  require_human_review:
    - patient_record_access

budget:                      # → Head 2: PennyPrompt config
  enforcement: atomic
  loop_detection:
    similarity_threshold: 0.85
    max_consecutive_similar: 3

execution:                   # → Head 3: ClawCrate profile
  default_profile: "safe"
  command_profiles:
    "npm install": "install"
    "cargo build": "build"
  denied_paths:
    - "/etc/**"
    - "**/.env"
    - "**/patient_records/**"
```

```bash
cerberus-policy compile policy/examples/healthcare-strict.yaml --out-dir ./compiled/
```

One change in one place propagates atomically to all three heads. No more "we updated the Lobster Trap rules but forgot to update the PennyPrompt budget cap."

---

## How CerberusGuard compares

|                                  | Head 1 (Prompt) | Head 2 (Budget) | Head 3 (Execution) | Local-first | Open source | Cross-layer policy |
|----------------------------------|:---------------:|:---------------:|:------------------:|:-----------:|:-----------:|:------------------:|
| **CerberusGuard**                | ✅ via Lobster Trap | ✅ via PennyPrompt | ✅ via ClawCrate | ✅ | ✅ MIT | ✅ |
| Lobster Trap (standalone)        | ✅ | ❌ | ❌ | ✅ | ✅ MIT | n/a |
| Docker container per agent       | partial | ❌ | partial (heavy) | ✅ | partial | ❌ |
| OpenAI Moderation API            | partial | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cloudflare AI Gateway            | partial | partial | ❌ | ❌ | ❌ | ❌ |
| LangChain Guardrails             | partial | ❌ | ❌ | in-process | ✅ | ❌ |
| Lakera Guard                     | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

Two structural advantages CerberusGuard alone has:

1. **Out-of-process in all three heads.** The agent can't disable what it doesn't control. In-process guards (LangChain Guardrails, etc.) are bypassable by the agent itself.
2. **Cross-layer policy as a single source of truth.** No other open-source project compiles one YAML to three independent enforcement engines.

---

## What this is, and what this isn't

**This is:**
- An integration layer for three best-in-class open-source primitives.
- Production-pathway (alpha now; hardening planned, see Roadmap).
- MIT-licensed end to end, including all three heads.
- Deployable on a single Linux or macOS machine — no cloud dependency, no API key beyond your LLM provider (and that can be Ollama local).

**This is not:**
- A replacement for Lobster Trap, PennyPrompt, or ClawCrate. They work fine standalone — CerberusGuard makes them work *together*.
- A managed service. You run it yourself.
- An anti-malware tool. We constrain agent misuse, not OS-level threats.
- A substitute for proper LLM application security review.

---

## Repository structure

```
CerberusGuard/
├── crates/
│   ├── cerberus-collector/        # Event collector HTTP server (Rust, axum, SQLite)
│   ├── cerberus-policy/           # Unified YAML → LT/PP/CC configs (Rust, clap)
│   └── cerberus-types/            # Shared TrustEvent schema (Rust)
├── sdk/
│   ├── python/                    # `cerberusguard` (pip)
│   └── typescript/                # `@cerberusguard/sdk` (npm)
├── dashboard/                     # Next.js 16 dashboard
├── policy/
│   ├── examples/                  # Sample policies (healthcare, finance, dev)
│   └── schema/                    # JSON Schema for policy validation
├── demo/
│   ├── attack-scenarios/          # Poisoned repos & malicious agent scripts
│   ├── docker-compose.yml         # Full stack for reviewers
│   └── run-demo.sh                # One-command end-to-end demo
├── infra/
│   ├── Dockerfile.collector
│   ├── Dockerfile.dashboard
│   └── systemd/                   # Service files for production deploy
├── backlog.yaml                   # Machine-readable execution backlog
├── CLAUDE.md                      # Operational guide for AI development agents
├── LICENSE                        # MIT
└── README.md                      # This file
```

---

## Roadmap

- [x] **v0.1 (alpha)** — unified event collector, policy compiler, dashboard, Python SDK, poisoned-repo demo
- [ ] TypeScript SDK parity with Python
- [ ] OpenTelemetry exporter (sink CerberusGuard events into existing OTel pipelines)
- [ ] Hosted demo on `cerberusguard.dev`
- [ ] Pre-built Docker images on `ghcr.io`
- [ ] One-click deploy template (Railway)
- [ ] `cerberus-policy lint` for policy linting and dry-run validation
- [ ] Audit export presets aligned with SOC2, ISO 27001, and the EU AI Act
- [ ] `HUMAN_REVIEW` workflow with email / Slack / PagerDuty approval channels
- [ ] Integration with [Arize](https://arize.com/) for ML observability sinks
- [ ] Multi-tenant Core for SOC team deployments

---

## Built on

CerberusGuard would not exist without these three projects. We extend them, we do not replace them:

- **[Lobster Trap](https://github.com/veeainc/lobstertrap)** by [Veea](https://veea.com) — the deep prompt inspection proxy that powers Head 1.
- **[PennyPrompt](https://github.com/manuelpenazuniga/PennyPrompt)** — atomic LLM budget enforcement and cost ledger; Head 2.
- **[ClawCrate](https://github.com/manuelpenazuniga/ClawCrate)** — kernel-level shell execution sandbox; Head 3.

Each is MIT-licensed, each runs standalone, and each is independently useful. CerberusGuard is the thin integration layer that turns them into one defensible product.

---

## Contributing

CerberusGuard is MIT-licensed and contributions are welcome.

```bash
git clone https://github.com/manuelpenazuniga/CerberusGuard.git
cd CerberusGuard
cargo build --workspace
cargo test --workspace
cargo clippy --workspace -- -D warnings
```

For agent-driven development (Claude Code, Cursor, Aider, etc.), read [`CLAUDE.md`](CLAUDE.md) first — it encodes the architectural invariants any contribution must respect.

---

## License

[MIT](LICENSE). Use it, fork it, ship it.

---

<div align="center">

*Built for the [TechEx AI & Big Data Expo North America Hackathon 2026](https://lablab.ai/ai-hackathons/techex-intelligent-enterprise-solutions-hackathon) — Track 1: Agent Security & AI Governance.*

</div>
