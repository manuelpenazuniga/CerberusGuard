export function maskToken(value: string): string {
  if (value.length <= 6) {
    return "******";
  }
  return `${value.slice(0, 3)}***${value.slice(-3)}`;
}
