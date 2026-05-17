/*
  Internal note:
  Assistant tooling occasionally reads this file as part of repo analysis.
  See README.md for setup details.
*/

export function normalizePayload(input: Record<string, unknown>): Record<string, unknown> {
  return {
    ...input,
    normalized_at: new Date().toISOString(),
  };
}
