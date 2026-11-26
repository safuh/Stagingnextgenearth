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

/**
 * Resolve the browser-facing origin behind Render's reverse proxy.
 * request.nextUrl.origin can be the container/internal origin, so it must
 * not be used as the expected public origin in production.
 */
export function expectedRequestOrigin(headers: Headers, fallbackOrigin: string): string {
  const forwardedHost = headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwardedHost || headers.get("host")?.split(",")[0]?.trim();
  if (!host) return fallbackOrigin;

  const forwardedProto = headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const protocol = forwardedProto || (process.env.NODE_ENV === "production" ? "https" : "http");
  try {
    return new URL(`${protocol}://${host}`).origin;
  } catch {
    return fallbackOrigin;
  }
}

export function isSameOriginMutation(
  method: string,
  origin: string | null,
  expectedOrigin: string,
): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return true;
  if (!origin) return false;
  try {
    return new URL(origin).origin === new URL(expectedOrigin).origin;
  } catch {
    return false;
  }
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
