import { NextRequest, NextResponse } from "next/server";

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
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
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
  const payload = await upstream.json().catch(() => ({})) as {
    subject?: string; access_token?: string; refresh_token?: string; detail?: string;
  };
  if (!upstream.ok || !payload.access_token || !payload.refresh_token || !payload.subject) {
    return NextResponse.json(
      { detail: payload.detail ?? "Unable to sign in" },
      { status: upstream.ok ? 502 : upstream.status },
    );
  }

  const response = NextResponse.json({ subject: payload.subject });
  response.cookies.set("nfe_access", payload.access_token, cookieOptions(
    Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60,
  ));
  response.cookies.set("nfe_refresh", payload.refresh_token, cookieOptions(
    Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400,
  ));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
