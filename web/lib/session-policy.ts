export type TokenPair = { access_token: string; refresh_token: string };

export function parseTokenPair(value: unknown): TokenPair | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const candidate = value as Record<string, unknown>;
  const access = candidate.access_token;
  const refresh = candidate.refresh_token;
  if (
    typeof access !== "string" ||
    typeof refresh !== "string" ||
    access.length === 0 ||
    refresh.length === 0 ||
    access.length > 16_384 ||
    refresh.length > 16_384 ||
    /\s/.test(access) ||
    /\s/.test(refresh)
  ) {
    return null;
  }
  return { access_token: access, refresh_token: refresh };
}

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
