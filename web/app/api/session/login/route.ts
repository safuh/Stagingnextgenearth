import { NextRequest, NextResponse } from "next/server";
import { isSameOriginMutation, parseTokenPair } from "@/lib/session-policy";

export const dynamic = "force-dynamic";

const API_BASE = (
  process.env.BACKEND_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000/api"
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
  if (!isSameOriginMutation(request.method, request.headers.get("origin"), request.nextUrl.origin)) {
    return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }

  let credentials: { identifier?: string; password?: string };
  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (!credentials.identifier || !credentials.password) {
    return NextResponse.json({ detail: "Identifier and password are required" }, { status: 422 });
  }

  const upstream = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });
  const payload: unknown = await upstream.json().catch(() => null);
  const tokenPair = parseTokenPair(payload);
  const subject = typeof payload === "object" && payload !== null && !Array.isArray(payload)
    ? (payload as Record<string, unknown>).subject
    : null;
  const detail = typeof payload === "object" && payload !== null && !Array.isArray(payload)
    ? (payload as Record<string, unknown>).detail
    : null;
  if (!upstream.ok || !tokenPair || typeof subject !== "string" || subject.length === 0) {
    return NextResponse.json(
      { detail: typeof detail === "string" ? detail : "Unable to sign in" },
      { status: upstream.ok ? 502 : upstream.status },
    );
  }

  const response = NextResponse.json({ subject });
  response.cookies.set("nfe_access", tokenPair.access_token, cookieOptions(
    Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60,
  ));
  response.cookies.set("nfe_refresh", tokenPair.refresh_token, cookieOptions(
    Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400,
  ));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
