export interface TokenResponse {
  subject: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
}

// Authentication cookies are HttpOnly and are deliberately inaccessible to JavaScript.
// The BFF validates protected requests and refreshes expired access tokens after a 401.
export function setSession(_tokens: TokenResponse): void {
  // Session cookies are set by /api/session/login.
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
    throw new Error(message);
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
