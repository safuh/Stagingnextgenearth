import { NextRequest, NextResponse } from "next/server";
import { isSameOriginMutation, parseTokenPair, safeApiPath, type TokenPair } from "@/lib/session-policy";

export const dynamic = "force-dynamic";

const API_BASE = (
  process.env.BACKEND_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000/api"
).replace(/\/$/, "");
const ACCESS_COOKIE = "nfe_access";
const REFRESH_COOKIE = "nfe_refresh";

type Tokens = TokenPair;

// Share a single rotating refresh operation across concurrent requests in this
// Node.js process; refresh tokens are single-use and parallel rotations race.
const refreshInFlight = new Map<string, { promise: Promise<Tokens | null>; expiresAt: number }>();

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    path: "/",
    maxAge,
  };
}

function applyTokens(response: NextResponse, tokens: Tokens) {
  response.cookies.set(
    ACCESS_COOKIE,
    tokens.access_token,
    cookieOptions(Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60),
  );
  response.cookies.set(
    REFRESH_COOKIE,
    tokens.refresh_token,
    cookieOptions(Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400),
  );
}

function clearTokens(response: NextResponse) {
  response.cookies.set(ACCESS_COOKIE, "", cookieOptions(0));
  response.cookies.set(REFRESH_COOKIE, "", cookieOptions(0));
}

async function sendUpstream(
  request: NextRequest,
  path: string,
  accessToken: string | undefined,
  body: ArrayBuffer | undefined,
): Promise<Response> {
  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");
  if (accept) headers.set("Accept", accept);
  if (contentType) headers.set("Content-Type", contentType);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  return fetch(`${API_BASE}/${path}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: hasBody ? body : undefined,
    cache: "no-store",
    redirect: "manual",
  });
}

async function refreshTokens(refreshToken: string): Promise<Tokens | null> {
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) return null;
  const payload: unknown = await response.json().catch(() => null);
  return parseTokenPair(payload);
}

function rotateRefreshToken(refreshToken: string): Promise<Tokens | null> {
  const existing = refreshInFlight.get(refreshToken);
  if (existing && existing.expiresAt > Date.now()) return existing.promise;
  if (existing) refreshInFlight.delete(refreshToken);

  const pending = refreshTokens(refreshToken);
  refreshInFlight.set(refreshToken, {
    promise: pending,
    expiresAt: Date.now() + 30_000,
  });
  const cleanup = setTimeout(() => {
    if (refreshInFlight.get(refreshToken)?.promise === pending) {
      refreshInFlight.delete(refreshToken);
    }
  }, 30_000);
  cleanup.unref?.();
  return pending;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!isSameOriginMutation(request.method, request.headers.get("origin"), request.nextUrl.origin)) {
    return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }

  const { path: segments } = await context.params;
  const path = safeApiPath(segments ?? []);
  if (!path) {
    return NextResponse.json({ detail: "Invalid API path" }, { status: 400 });
  }
  if (["auth/login", "auth/refresh", "auth/logout"].includes(path)) {
    return NextResponse.json({ detail: "Use the session endpoints for authentication" }, { status: 404 });
  }

  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  let upstream = await sendUpstream(request, path, accessToken, body);
  let rotated: Tokens | null = null;

  if (upstream.status === 401 && refreshToken) {
    rotated = await rotateRefreshToken(refreshToken);
    if (rotated) {
      accessToken = rotated.access_token;
      upstream = await sendUpstream(request, path, accessToken, body);
    }
  }

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  const disposition = upstream.headers.get("content-disposition");
  if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
  if (disposition) responseHeaders.set("content-disposition", disposition);
  responseHeaders.set("Cache-Control", "no-store");

  const response = new NextResponse(
    upstream.status === 204 ? null : upstream.body,
    { status: upstream.status, headers: responseHeaders },
  );
  if (rotated) applyTokens(response, rotated);
  else if (upstream.status === 401 && refreshToken) clearTokens(response);
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
