export function formatPrice(p?: number): string | null {
  if (p === undefined || p === null) return null;
  return p === 0 ? "Free to Play" : `$${p.toFixed(2)}`;
}
