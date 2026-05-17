# Demo Safety Notes

This repository includes a simulated malicious package under
`demo/attack-scenarios/poisoned-repo/` for controlled security demonstrations.

## Why this is safe to commit

1. Exfiltration target is `evil.example.com`, a reserved non-production domain.
2. No script includes real credentials or real endpoints.
3. The code is inert unless someone intentionally runs the demo flow.

## Safe execution guidance

1. Run only in an isolated development environment.
2. Do not replace `evil.example.com` with any real domain.
3. For local baseline demos, route `evil.example.com` to localhost honeypot
   only inside your own machine.
4. Never run these scripts against production hosts or real secrets.

## Files covered

- `README.md` (contains explicit prompt injection marker)
- `package.json` (`postinstall` hook used as attack simulation)
- `scripts/setup.js` (simulated secret read + exfil attempt)
- `src/*.ts` and `tests/*.ts` (context scaffolding)
