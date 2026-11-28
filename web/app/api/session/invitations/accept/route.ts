import { NextRequest, NextResponse } from "next/server";
import { expectedRequestOrigin, isSameOriginMutation, parseTokenPair } from "@/lib/session-policy";

export const dynamic = "force-dynamic";

const API_BASE = (
  process.env.BACKEND_API_URL ??
  (process.env.BACKEND_API_HOSTPORT
    ? `http://${process.env.BACKEND_API_HOSTPORT}/api`
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api")
).replace(/\/$/, "");

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    path: "/",
    maxAge,
  };
}

export async function POST(request: NextRequest) {
  if (!isSameOriginMutation(request.method, request.headers.get("origin"), expectedRequestOrigin(request.headers, request.nextUrl.origin))) {
    return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }
  let body: { token?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (!body.token || !body.password) {
    return NextResponse.json({ detail: "Invitation token and password are required" }, { status: 422 });
  }
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/auth/invitations/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Onboarding service is temporarily unavailable." }, { status: 502 });
  }
  const payload: unknown = await upstream.json().catch(() => null);
  const tokens = parseTokenPair(payload);
  const data = typeof payload === "object" && payload !== null && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {};
  if (!upstream.ok || !tokens || typeof data.subject !== "string") {
    const nestedError = typeof data.error === "object" && data.error !== null
      ? data.error as Record<string, unknown>
      : {};
    const detail = typeof data.detail === "string"
      ? data.detail
      : typeof nestedError.message === "string"
        ? nestedError.message
        : "Unable to accept this invitation";
    return NextResponse.json({ detail }, { status: upstream.ok ? 502 : upstream.status });
  }
  const response = NextResponse.json({ roles: Array.isArray(data.roles) ? data.roles : [] });
  response.cookies.set("nfe_access", tokens.access_token, cookieOptions(
    Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60,
  ));
  response.cookies.set("nfe_refresh", tokens.refresh_token, cookieOptions(
    Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400,
  ));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
