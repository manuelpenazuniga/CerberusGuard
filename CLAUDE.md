# CLAUDE.md — Operational Guide for AI Development Agents

> **Read this file in full before writing any code in this repository.**
> If anything in your training conflicts with this document, **this document wins**.
> The constraints here are deliberate and load-bearing.

This is the operational guide for Claude Code (or any other AI agent — Cursor, Aider, Sourcegraph Cody, Cline) working on **CerberusGuard** during and after the TechEx 2026 hackathon sprint.

It contains:

1. The mental model — what CerberusGuard is, and what it isn't
2. Architectural invariants (non-negotiable)
3. Build order for the compressed sprint
4. Coding standards specific to this repository
5. Decision rules when you're stuck
6. Anti-patterns to avoid
7. Pre-commit verification checklist
8. Where to look when you don't know something

---

## 0. First things first

| Thing | Value |
|---|---|
| Project name | **CerberusGuard** |
| GitHub repo | `https://github.com/manuelpenazuniga/CerberusGuard` |
| Hackathon | TechEx 2026 — Track 1 (Agent Security & AI Governance) |
| **Hard deadline** | **2026-05-19 17:00 PDT** (San Jose, CA) |
| Primary prize target | **Veea Award** (Track 1 winner) |
| Primary owner | Manuel Peña (solo builder) |
| Source-of-truth for plans | `docs/AGENTTRUST_PROJECT.md`, `docs/AGENTTRUST_ROADMAP_TECHEX.md`, and `backlog.yaml` |
| Source-of-truth for execution | `backlog.yaml` (machine-readable, atomic tasks) |

> The `docs/` directory is **gitignored** — it contains the original hackathon brief, the detailed project definition, the 5-day roadmap, and the seed README/CLAUDE drafts authored by Opus 4.7. They are private strategy artifacts. Public architecture and threat-model documentation will live elsewhere (TBD: `documentation/` or GitHub wiki).
>
> The strategic docs still use the project's original draft name, **"AgentTrust Stack"**. The project has since been re-branded to **CerberusGuard** to match the GitHub repo and to take advantage of the three-headed-dog metaphor that maps cleanly to the three security layers. **Substance is unchanged.** When you read `AGENTTRUST_*.md`, mentally substitute "CerberusGuard".

---

## 1. Mental model: read before doing anything

### 1.1 What CerberusGuard is

CerberusGuard is **an integration layer**, not a new product. It unifies three pre-existing open-source primitives:

- **Lobster Trap** (Go, MIT, by Veea) — deep prompt inspection proxy
- **PennyPrompt** (Rust, MIT, Manuel's prior project) — atomic LLM budget proxy with cost ledger
- **ClawCrate** (Rust, MIT, Manuel's prior project) — kernel-level shell execution sandbox

All three already work standalone. **We do not modify their source code.** We integrate them by:

1. Tailing their audit logs and forwarding events to our Core collector in a unified schema
2. Compiling a single YAML policy to three separate configs (one per head)
3. Providing a dashboard and SDKs that correlate events by `correlation_id`

If you find yourself wanting to modify Lobster Trap, PennyPrompt, or ClawCrate source code — **stop**. That is almost certainly the wrong move. The right move is to add an adapter, a wrapper, or a config layer in this repository.

### 1.2 Hackathon context

This repo is built in a compressed sprint for a hackathon judged by enterprise security engineers (PayPal, JP Morgan, Meta, Apple, Google Cloud, IBM, Workday — see `docs/techex-intelligent-enterprise-solutions-hackathon.md` for the full list).

| Judging criterion | Weight (informal) | What it means for the code |
|---|---|---|
| Application of Technology | 40 % | Lobster Trap, PennyPrompt, and ClawCrate must all be **visibly working** end to end. Not mocked. |
| Presentation              | 20 % | README and demo must be clean. Polish wins over feature count. |
| Business Value            | 25 % | Enterprise framing throughout. SOC2, audit export, regulated industries. |
| Originality               | 15 % | The unified policy compiler and cross-layer correlation are the original contributions. Emphasize them. |

We are competing specifically for the **Veea Award**. Veea engineers will read this code. Be respectful of Lobster Trap as the foundation — we extend, we do not replace.

### 1.3 The narrative we are building

> "Three open-source primitives, unified for the first time.
> Lobster Trap solves the prompt layer. PennyPrompt solves the budget layer. ClawCrate solves the execution layer.
> CerberusGuard turns three best-in-class tools into one defensible enterprise product."

Every line of code, every commit message, every doc paragraph should be consistent with this narrative. Anything that suggests "we built our own prompt inspection" or "we're replacing Lobster Trap" is wrong direction.

### 1.4 Solo-builder context (critical scope cut)

The 5-day roadmap in `docs/AGENTTRUST_ROADMAP_TECHEX.md` was sized for a 2-3 person team. Manuel is solo. The roadmap explicitly says "if you're solo, skip TechEx" — we are proceeding anyway, with these aggressive cuts:

- ❌ **Drop**: TypeScript SDK (Python only)
- ❌ **Drop**: 2 of the 3 example policies (keep `healthcare-strict.yaml`, drop the others)
- ❌ **Drop**: Cross-layer timeline visualisation in dashboard (keep a flat live feed with correlation filter)
- ❌ **Drop**: Custom landing page (the dashboard at `:3000` is the landing page)
- ❌ **Drop**: Docker pre-built images on `ghcr.io` (docker-compose is enough)
- ✅ **Keep, no compromise**: the poisoned-repo demo, the policy compiler, the unified event schema, the Python SDK, the dashboard live feed, the README/CLAUDE/backlog, the YouTube video, the Devpost writeup

If any task in `backlog.yaml` conflicts with a cut above, the cut wins.

---

## 2. Architectural invariants — non-negotiable

These are constraints that override any other consideration. If you find yourself violating one, **stop and re-read this section**.

### 2.1 Three heads are orthogonal, not a single chain

- Head 1 (Lobster Trap) and Head 2 (PennyPrompt) are **in series** on the HTTP path: `agent → LT → PP → LLM`
- Head 3 (ClawCrate) is **parallel**: it intercepts `exec()`, not HTTP

Never describe ClawCrate as "in the chain". Never put it between LT and PP. Never imply the LLM call path passes through ClawCrate.

### 2.2 Out-of-process across all three heads

The whole value prop is that the agent cannot disable any head. This means:

- ❌ Head enforcement inside the agent process (in-process middleware, library guards)
- ❌ Head enforcement through libraries the agent imports
- ✅ Head enforcement through standalone binaries the agent talks to via HTTP or process boundary

If you propose anything that runs inside the agent's process, you're breaking the core invariant.

### 2.3 The event schema is the contract

Every event from every head serialises to `cerberus_types::TrustEvent`. Layer-specific data goes into the free-form `payload: serde_json::Value` field, never into new top-level fields.

Why: this is what makes cross-layer correlation possible. If each head has a different shape, the dashboard becomes three dashboards.

### 2.4 The Core collector is stateless about decisions

The collector receives events. It does **not** make security decisions. It does not "approve" or "deny" anything. It is observability infrastructure.

Don't add policy logic to the collector. Policy lives in YAML, gets compiled to LT/PP/CC configs, and is enforced by the data planes.

### 2.5 The Core is opt-in

Lobster Trap, PennyPrompt, and ClawCrate all work without the Core collector. **Killing the Core must not block any head.** Adapters fail open: if the collector is unreachable, they log the error and continue.

This is critical for enterprise pitching: "CerberusGuard adds observability; it does not become a single point of failure."

### 2.6 We do not store raw secrets

The collector receives events. Some payloads describe what was blocked. **Never store the actual prompt content** if it contains credentials, PII, or sensitive data. Use redacted hashes, pattern matches, or summarised metadata. If you find yourself writing `payload.prompt = req.body` — stop.

### 2.7 Latency budget

Total added latency across Head 1 + Head 2 must be < **50 ms p95** on a typical workload. Lobster Trap is sub-ms by design. PennyPrompt's budget check is a single SQLite read. Adapter HTTP POSTs to the Core are **async fire-and-forget** — they must never block the agent's request path.

If you write `await collector.post(event)` in the critical path, that's a bug. Use a queue + background flush.

### 2.8 Storage: SQLite first, DuckDB later

The original draft in `AGENTTRUST_PROJECT.md` proposed DuckDB. We're starting with **SQLite + JSON1** instead. Reasons:

- DuckDB Rust bindings have a history of build instability on macOS arm64 (Manuel's primary dev environment).
- SQLite is in `std`-adjacent stable territory; zero risk of build failures eating sprint hours.
- The query patterns we need (filter by `correlation_id`, group by layer/verdict, time-window scans) are well within SQLite's comfort zone for our event volume.
- We can swap to DuckDB later if analytical queries become the bottleneck.

If you see `duckdb` in dependency suggestions, replace with `rusqlite` + `serde_json`.

---

## 3. Build order (compressed sprint)

`backlog.yaml` is the source of truth for tasks. The sequence below is the high-level shape; the YAML breaks each step into atomic tasks with IDs, dependencies, and acceptance criteria.

### Day 1 — Foundation (compressed: today + tonight)
**Goal:** Stack base functional end-to-end. Each component starts, talks to the next, emits events to the collector.

Key deliverables:
- Cargo workspace with `cerberus-types`, `cerberus-collector`, `cerberus-policy`
- `cerberus-types`: TrustEvent schema with serialisation tests passing
- `cerberus-collector`: axum HTTP server on `:9090`, SQLite-backed, `/events` POST + GET, `/health`, `/correlations/:id`
- External primitives (`external/lobstertrap`, `external/pennyprompt`, `external/clawcrate`) cloned and building
- Python adapter for Lobster Trap log → Core collector (fail-open)
- Next.js 16 dashboard skeleton polling `/events`

### Day 2 — Three heads integrated
**Goal:** Full chain in series, policy compiler operational, cross-layer correlation visible.

Key deliverables:
- `agent → LT (:8080) → PP (:8787) → Ollama (:11434)` chain working
- `cerberus-policy compile` produces three valid configs from one YAML
- At least one example policy (`healthcare-strict.yaml`) compiles cleanly
- ClawCrate adapter (watches `~/.clawcrate/runs/`)
- Python SDK `cerberusguard` with `CerberusClient` (LLM + exec, shared `correlation_id`)
- Dashboard renders cross-layer correlation by filtering on `correlation_id`

### Day 3 — Demo (the critical day)
**Goal:** Poisoned-repo attack scenario works end-to-end and looks good on video.

Key deliverables:
- `demo/attack-scenarios/poisoned-repo/` with plausible package.json + hidden prompt injection + simulated exfiltration target
- Honeypot setup so "without CerberusGuard" demonstrably leaks secrets (in an isolated env)
- `demo/run-malicious-agent.py` with `--mode unprotected | protected`
- `demo/run-demo.sh` one-command end-to-end
- Dashboard polish: red-flash on DENY, summary banner, color coding
- First screen-recorded run

### Day 4 — Materials (no code changes except bug fixes)
- Final smoke test on a clean clone
- Video grabbed (3-5 min, voiceover, screen capture)
- Slide deck (PDF, 5-10 slides)
- Devpost / Lablab.ai writeup (1,000-1,500 words)
- README screenshots refreshed

### Day 5 — Submit
- Final smoke at 10:00 PDT, submit at 11:00 PDT, **do not wait** for the 17:00 deadline

---

## 4. Coding standards specific to this repo

### 4.1 Rust

- `cargo clippy --workspace -- -D warnings` must pass before every commit. No `#[allow(...)]` without a justifying comment.
- Errors: `anyhow::Result` for binary crates, `thiserror`-derived enums for library crates.
- Async: prefer `tokio::spawn` over hand-rolled `Future`s.
- No `unwrap()` outside of tests and `main.rs` boot sequence.
- No `expect()` outside of `main.rs`. Use proper error propagation.
- Crate names: `cerberus-types`, `cerberus-collector`, `cerberus-policy` (short prefix; the GitHub repo name carries the full brand).

### 4.2 Python

- Type hints everywhere. `from __future__ import annotations` at the top of every file.
- Use `httpx`, not `requests`. Connection pooling matters in adapters.
- Errors go to stderr explicitly: `print(..., file=sys.stderr)`.
- Adapters are invoked as modules: `python -m cerberusguard.adapters.lobstertrap`. Do not install adapters as global binaries.

### 4.3 TypeScript

- Strict mode on (`"strict": true`).
- No `any`. Use `unknown` and narrow.
- Prefer `node:` prefix for built-ins (`node:fs`, `node:path`).

### 4.4 Commit messages

```
<type>: <subject>

[optional body]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. Subject in the imperative present tense, < 60 chars.

**No co-author lines from Claude. No emojis in commits.** No `Generated-with-Claude` footers. Manuel is the author. We can attribute in the writeup, not in every commit.

### 4.5 No silent mocks

If you write a stub or mock, mark it visibly:

```rust
// TODO(hackathon): mock implementation, replace before production
#[doc(hidden)]
pub fn mock_thing() -> ... { ... }
```

Track every TODO as a backlog task (`backlog.yaml` entry with `status: pending`). Don't leave silent mocks.

---

## 5. Decision rules when stuck

### 5.1 "Should I add this feature?"

Default answer: **no**.

After Day 2, the answer is always no unless the change directly improves the demo or the README's first three screens. Polish > features. The judges score on what they see, not on what's in the code.

### 5.2 "This library would solve my problem but it's heavy"

Check `cargo tree -e normal | wc -l` or `npm ls --all | wc -l`. As a rule of thumb:

- Adds < 50 transitive packages — fine
- Adds 50-200 — strongly justify in the commit message
- Adds 200+ — find another way

Heavy dependencies make `./demo/run-demo.sh` slow on first clone. Slow demos kill judge experience.

### 5.3 "Lobster Trap behaviour surprised me"

Re-read the [Lobster Trap README](https://github.com/veeainc/lobstertrap/blob/main/README.md). Understand the bidirectional metadata header convention. Run `lobstertrap inspect "<prompt>"` to see DPI output.

If LT does something we don't expect, it's almost certainly correct and our adapter is wrong.

### 5.4 "My change broke the demo"

Revert. Use `git reflog` if needed.

```bash
git reset --hard <last-known-good-commit>
```

The hackathon clock is a more powerful constraint than the temptation to fix one more thing.

### 5.5 "Should I optimise this code path?"

Only if benchmarks show p95 latency > 50 ms. Otherwise, leave it.

### 5.6 "I want to refactor X"

After Day 2, refactoring is forbidden unless it's required to fix a demo-blocking bug. Even then, smallest possible change. Refactors before submission are how hackathons get lost.

### 5.7 "Should I ask Manuel before doing this?"

Ask before:

- Renaming anything that appears in `README.md` (badges, URLs, screenshots)
- Adding a new external service dependency (Vercel, Railway, ghcr.io, Sentry, etc.)
- Anything that requires Manuel to log into a third-party account
- Any change to `backlog.yaml` semantics (adding/removing epics, changing status fields)
- Pushing to `main` if the previous commit hasn't been smoke-tested

Don't ask before: implementing tasks already listed in `backlog.yaml`, fixing your own typos, running `cargo test`.

---

## 6. Anti-patterns (do not do these)

### 6.1 Don't modify Lobster Trap, PennyPrompt, or ClawCrate source

We extend them through configuration and adapters, not source modification. If we ever send a PR upstream, that's a separate body of work.

### 6.2 Don't reimplement DPI

Lobster Trap already does deep prompt inspection. We don't add a second regex layer. We don't add LLM-based classification as an alternative (LT is sub-ms; LLM classification is hundreds of ms).

### 6.3 Don't bypass the collector for "performance"

Adapters POST events. Period. If performance is bad, fix the adapter (batch, async queue). Don't write a parallel direct-to-DB path.

### 6.4 Don't add cloud dependencies

The whole stack runs on a single machine. No required SaaS. No required API keys beyond the LLM provider (and even that can be Ollama local).

### 6.5 Don't market-speak in code or docs

This is technical infrastructure for security engineers. Avoid:

- ❌ "Revolutionary AI safety platform"
- ❌ "Enterprise-grade trust solutions"
- ❌ Emojis in code, in commit messages, or in technical doc headings
- ✅ "Three-head defence, MIT-licensed, deployable today"

The README is allowed to be visually polished (badges, ASCII diagrams, comparison tables). It is not allowed to be hyperbolic.

### 6.6 Don't claim production-ready

We're alpha. Say "production-pathway" or "deployable today, hardening planned". Claiming "production-ready" without years of operation is a credibility hit in front of security-savvy judges.

### 6.7 Don't compete with Lobster Trap

In every doc, every commit message, every video frame: CerberusGuard **extends** Lobster Trap. The Veea panel will read our submission. They will spot any framing that positions us as a competitor.

### 6.8 Don't ignore the gitignore

`docs/` is private. `external/` is large and rebuildable. `.env` and credentials never get committed. If you `git add .` and see anything from these paths staged, **abort and review** before committing.

---

## 7. Pre-commit verification checklist

Before `git push`:

- [ ] `cargo build --workspace --release` succeeds
- [ ] `cargo test --workspace` passes
- [ ] `cargo clippy --workspace -- -D warnings` is clean
- [ ] If touched Python: tests pass (when tests exist), `ruff check` is clean
- [ ] If touched TypeScript: `npm run build` in `dashboard/` succeeds
- [ ] Commit message follows §4.4 (no Claude footer, no emoji, imperative subject)
- [ ] No new TODO without a tracked task in `backlog.yaml`
- [ ] No new `unwrap()` / `expect()` outside `main.rs` or tests
- [ ] No accidental commit of `.env`, `target/`, `node_modules/`, `external/`, `docs/`, or `*.duckdb` / `*.sqlite` files

---

## 8. Memory & state for future sessions

Claude Code maintains a persistent memory directory keyed to this workspace at:

```
~/.claude/projects/-Volumes-MacMiniExt-dev-OpenSource-Projects-CerberusGuard-CerberusGuard/memory/
```

Three memories are already seeded by the bootstrap session (Manuel's profile, the hackathon context, the architectural invariants). When you (Sonnet 4.6 or a future Opus session) start a new conversation, **read `MEMORY.md` first** — it is the index, and the files it links to are the durable context that survives compaction.

When you learn something durable (a new convention, a user preference, an architectural decision), write it to a new memory file and add a one-line pointer to `MEMORY.md`. Do not duplicate code-derivable facts (file layouts, function signatures) — read the code for those.

---

## 9. When you don't know something

This document is the source of truth, but it's incomplete. When you encounter something not covered:

1. **Re-read this document.** Many questions are answered here and you missed it.
2. **Read `backlog.yaml`** — it lists every planned task with explicit acceptance criteria and references.
3. **Check `docs/AGENTTRUST_PROJECT.md`** (gitignored, available locally) — it has full architectural detail and code templates.
4. **Check `docs/AGENTTRUST_ROADMAP_TECHEX.md`** for time-and-priority decisions and the per-day scope-cut rules.
5. **Read the [Lobster Trap README](https://github.com/veeainc/lobstertrap)**. Veea's docs are short and dense; read them all.
6. **Reuse from Manuel's prior repos** when applicable: `PennyPrompt` (`/Volumes/MacMiniExt/dev/OpenSource Projects/PennyPrompt/PennyPrompt`) and `ClawCrate` (`/Volumes/MacMiniExt/dev/OpenSource Projects/ClawCrate`) are read-only references for SDK ergonomics, log formats, and Rust idioms.
7. **Ask Manuel.** Don't guess on architectural decisions. Use `AskUserQuestion` if you have access to it.

If a tool you'd normally use isn't available in this environment, ask. Don't fake outputs.

---

## 10. Final reminders

- Hackathon deadline: **2026-05-19 17:00 PDT** (San Jose, CA). Today is **2026-05-16** — you have roughly three working days, not five.
- We are competing for the **Veea Award** in Track 1. Everything else (1st/2nd/3rd overall) is secondary.
- Veea engineers will read this code. Be respectful and clear.
- Tone throughout: **enterprise, sober, technical**. Not marketing. Not casual.
- If something doesn't work, document it as roadmap. Don't lie about what's built.

> "Three open-source primitives, unified for the first time. Built on Veea's Lobster Trap. Deployable today."

That's the line. Everything supports it.

Now build.
