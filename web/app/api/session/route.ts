import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  // This endpoint is intentionally read-only. Refresh-token rotation is performed
  // by the API proxy only when an access-token request receives 401, avoiding
  // concurrent refresh races during React Strict Mode/session restoration.
  const authenticated = Boolean(
    request.cookies.get("nfe_access")?.value &&
    request.cookies.get("nfe_refresh")?.value,
  );
  const response = NextResponse.json({ authenticated });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
