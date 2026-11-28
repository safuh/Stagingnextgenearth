import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE = (
  process.env.BACKEND_API_URL ??
  (process.env.BACKEND_API_HOSTPORT
    ? `http://${process.env.BACKEND_API_HOSTPORT}/api`
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api")
).replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const requestedPortal = request.nextUrl.searchParams.get("portal");
  const portal = requestedPortal === "learner" ? "learner" : "staff";
  try {
    const upstream = await fetch(`${API_BASE}/auth/google/start?portal=${portal}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!upstream.ok) {
      const destination = new URL(portal === "learner" ? "/learners/sign-in" : "/staff/login", request.nextUrl.origin);
      destination.searchParams.set("error", upstream.status === 503 ? "google_not_configured" : "google_signin_failed");
      return NextResponse.redirect(destination);
    }
    const payload = (await upstream.json()) as { authorization_url?: string };
    if (!payload.authorization_url || !payload.authorization_url.startsWith("https://accounts.google.com/")) {
      throw new Error("Invalid Google authorization URL");
    }
    const authorizationUrl = new URL(payload.authorization_url);
    const state = authorizationUrl.searchParams.get("state");
    if (!state || state.length < 32) throw new Error("Missing Google OAuth state");
    const response = NextResponse.redirect(authorizationUrl);
    const stateCookieOptions = {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax" as const,
      path: "/",
      maxAge: 600,
    };
    response.cookies.set("nfe_google_state", state, stateCookieOptions);
    response.cookies.set("nfe_google_portal", portal, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 600,
    });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    const destination = new URL(portal === "learner" ? "/learners/sign-in" : "/staff/login", request.nextUrl.origin);
    destination.searchParams.set("error", "google_signin_failed");
    return NextResponse.redirect(destination);
  }
}
