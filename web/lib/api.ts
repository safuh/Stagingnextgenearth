export interface TokenResponse {
  subject: string;
  access_token?: string;
  refresh_token?: string;
}

export interface RegistrationResponse {
  subject: string;
}

export interface AuthenticationMembership {
  membership_id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: string;
  roles: string[];
  status: "active" | "invited";
}

export interface AuthenticationContext {
  user_id: string;
  identifier: string;
  memberships: AuthenticationMembership[];
}

export interface ApiError {
  detail?: string;
  message?: string;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, Math.ceil(seconds));
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return undefined;
  return Math.max(0, Math.ceil((timestamp - Date.now()) / 1000));
}

// Authentication cookies are HttpOnly and are deliberately inaccessible to JavaScript.
// The BFF validates protected requests and refreshes expired access tokens after a 401.
export function setSession(_tokens: TokenResponse): void {
  // Session cookies are set by /api/session/login.
  void _tokens;
}

export function clearSession(): void {
  // Compatibility for portal sign-out controls; cookies remain server-managed.
  void fetch("/api/session/logout", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    keepalive: true,
  }).catch(() => undefined);
}

export function hasSession(): boolean {
  // The browser cannot inspect HttpOnly cookies; protected requests determine session validity.
  return true;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiError;
      message = body.detail ?? body.message ?? message;
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new ApiRequestError(
      message,
      response.status,
      parseRetryAfter(response.headers.get("retry-after")),
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

export async function getAuthenticationContext(): Promise<AuthenticationContext> {
  return apiGet<AuthenticationContext>("/auth/context");
}

export async function register(identifier: string, password: string): Promise<RegistrationResponse> {
  return request<RegistrationResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
}

export async function login(identifier: string, password: string): Promise<TokenResponse> {
  const response = await fetch("/api/session/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify({ identifier, password }),
  });
  if (!response.ok) {
    let message = `Sign-in failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiError;
      message = body.detail ?? body.message ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }
  return (await response.json()) as TokenResponse;
}

export async function restoreSession(): Promise<TokenResponse | null> {
  const response = await fetch("/api/session", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) return null;
  const result = (await response.json()) as { authenticated: boolean };
  return result.authenticated ? { subject: "" } : null;
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/session/logout", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Unable to complete sign-out.");
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export async function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}


type RevalidatedValue = { etag: string; value: unknown };
const publicGetCache = new Map<string, RevalidatedValue>();

/** Revalidate a public GET using its ETag; reuse the cached representation on 304. */
export async function apiGetRevalidated<T>(path: string): Promise<T> {
  const cached = publicGetCache.get(path);
  const headers = new Headers({ Accept: "application/json" });
  if (cached) headers.set("If-None-Match", cached.etag);
  const response = await fetch(`/api/backend${path}`, {
    method: "GET", headers, credentials: "same-origin", cache: "no-store",
  });
  if (response.status === 304) {
    if (!cached) throw new Error("Received a 304 response without a cached representation.");
    return cached.value as T;
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiError;
      message = body.detail ?? body.message ?? message;
    } catch { /* retain status-based message */ }
    throw new Error(message);
  }
  const value = (await response.json()) as T;
  const etag = response.headers.get("ETag");
  if (etag) publicGetCache.set(path, { etag, value });
  else publicGetCache.delete(path);
  return value;
}
