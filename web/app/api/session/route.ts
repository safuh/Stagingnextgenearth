import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE = (
  process.env.BACKEND_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000/api"
).replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const refreshToken = request.cookies.get("nfe_refresh")?.value;
  if (!refreshToken) {
    return NextResponse.json({ authenticated: false }, { headers: { "Cache-Control": "no-store" } });
  }

  const upstream = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  const payload = await upstream.json().catch(() => ({})) as {
    subject?: string; access_token?: string; refresh_token?: string;
  };

  if (!upstream.ok || !payload.subject || !payload.access_token || !payload.refresh_token) {
    const response = NextResponse.json({ authenticated: false });
    const expired = {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict" as const,
      path: "/",
      maxAge: 0,
    };
    response.cookies.set("nfe_access", "", expired);
    response.cookies.set("nfe_refresh", "", expired);
    response.headers.set("Cache-Control", "no-store");
    return response;
  }

  const response = NextResponse.json({ authenticated: true, subject: payload.subject });
  response.cookies.set("nfe_access", payload.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60,
  });
  response.cookies.set("nfe_refresh", payload.refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400,
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
