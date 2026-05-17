# Demo Safety Notes

This repository includes a *simulated* malicious package under
`demo/attack-scenarios/poisoned-repo/` for controlled security demonstrations.

## Why this is safe to commit and safe to run

1. **Exfiltration target is `evil.example.com`** — a reserved, non-production
   IETF-controlled domain that does not resolve. Even if the postinstall ran
   to completion, the HTTPS POST would fail at DNS resolution.

2. **The postinstall does not read credential contents.** Earlier drafts
   of `scripts/setup.js` actually called `fs.readFileSync()` on
   `~/.ssh/id_rsa` and `~/.aws/credentials`. We deliberately removed that:
   the current script only checks `fs.statSync().isFile()` and reports
   *presence* (true/false), never bytes. An operator who runs the
   unprotected scenario on a workstation with real credentials cannot have
   them captured even into process memory.

3. **No real endpoints or real credentials anywhere in the package.**

4. **The code is inert unless `npm install` is executed.** `package.json`
   declares no dependencies, so the install completes in under a second
   purely to trigger the `postinstall` hook.

## What the demo actually demonstrates

| Layer | Where it blocks | Evidence the audience sees |
|---|---|---|
| Lobster Trap (LT) | Reads the poisoned `README.md` and refuses to send the prompt to the LLM | `verdict: DENY`, `rule: block_obfuscation_evasion`, `target_paths`, `target_domains` in the LT audit event |
| ClawCrate (CC) | Wraps `npm install` so the `postinstall` script runs inside a Landlock/Seatbelt sandbox that denies access to `~/.ssh` and `~/.aws` | `denied_paths_accessed > 0` in the CC audit event; the `existsSafe()` check returns `false` despite the host having the files |

Both blocks are real. The simulated-exfil note in `setup.js` is
defence-in-depth for the operator — it does not weaken the demonstration.

## Safe execution guidance

1. Run only in an isolated development environment.
2. Do not replace `evil.example.com` with a real domain.
3. For local baseline demos, route `evil.example.com` to a localhost
   honeypot (see `demo/honeypot-setup.sh`) — never to a public host.
4. Never run these scripts against production hosts or against real secrets.

## Files covered

- `README.md` — contains explicit prompt-injection marker for LT to detect.
- `package.json` — `postinstall` hook used as the attack vector.
- `scripts/setup.js` — simulated exfil attempt (presence-only, see point 2 above).
- `src/*.ts` and `tests/*.ts` — context scaffolding so the package looks plausible.
