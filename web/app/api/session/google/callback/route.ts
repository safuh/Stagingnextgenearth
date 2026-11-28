import { NextRequest, NextResponse } from "next/server";
import { parseTokenPair } from "@/lib/session-policy";

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
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");
  const requestedPortal = request.cookies.get("nfe_google_portal")?.value;
  const browserState = request.cookies.get("nfe_google_state")?.value;
  const failurePath = requestedPortal === "learner" ? "/learners/sign-in" : "/staff/login";
  if (!code || !state || !browserState || state !== browserState || error) {
    const response = NextResponse.redirect(new URL(`${failurePath}?error=google_signin_failed`, request.nextUrl.origin));
    response.cookies.delete("nfe_google_portal");
    response.cookies.delete("nfe_google_state");
    return response;
  }
  try {
    const upstream = await fetch(
      `${API_BASE}/auth/google/callback?${new URLSearchParams({ code, state })}`,
      { method: "GET", headers: { Accept: "application/json" }, cache: "no-store" },
    );
    const payload: unknown = await upstream.json().catch(() => null);
    const tokens = parseTokenPair(payload);
    const data = typeof payload === "object" && payload !== null && !Array.isArray(payload)
      ? payload as Record<string, unknown>
      : {};
    if (!upstream.ok || !tokens || typeof data.subject !== "string") {
      const response = NextResponse.redirect(new URL(`${failurePath}?error=google_signin_failed`, request.nextUrl.origin));
      response.cookies.delete("nfe_google_portal");
      response.cookies.delete("nfe_google_state");
      return response;
    }
    const destination = data.portal === "learner" ? "/learners" : "/workspace";
    const response = NextResponse.redirect(new URL(destination, request.nextUrl.origin));
    response.cookies.set("nfe_access", tokens.access_token, cookieOptions(
      Number(process.env.ACCESS_TOKEN_MINUTES ?? 15) * 60,
    ));
    response.cookies.set("nfe_refresh", tokens.refresh_token, cookieOptions(
      Number(process.env.REFRESH_TOKEN_DAYS ?? 14) * 86400,
    ));
    response.cookies.delete("nfe_google_portal");
    response.cookies.delete("nfe_google_state");
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    const response = NextResponse.redirect(new URL(`${failurePath}?error=google_signin_failed`, request.nextUrl.origin));
    response.cookies.delete("nfe_google_portal");
    response.cookies.delete("nfe_google_state");
    return response;
  }
}
