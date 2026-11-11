export function isSameOriginMutation(
  method: string,
  origin: string | null,
  expectedOrigin: string,
): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return true;
  return origin === expectedOrigin;
}

export function safeApiPath(segments: string[]): string | null {
  if (
    segments.length === 0 ||
    segments.some((segment) => segment.length === 0 || segment === "." || segment === "..")
  ) {
    return null;
  }
  return segments.map((segment) => encodeURIComponent(segment)).join("/");
}
