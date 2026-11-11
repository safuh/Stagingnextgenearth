const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "");

export interface TokenResponse {
  subject: string;
  access_token: string;
  refresh_token: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
}

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setSession(tokens: TokenResponse): void {
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
}

export function clearSession(): void {
  accessToken = null;
  refreshToken = null;
}

export function hasSession(): boolean {
  return accessToken !== null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
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

export async function login(identifier: string, password: string): Promise<TokenResponse> {
  const tokens = await request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
  setSession(tokens);
  return tokens;
}

export async function logout(): Promise<void> {
  const currentRefreshToken = refreshToken;
  clearSession();
  if (!currentRefreshToken) return;
  await request<void>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: currentRefreshToken }),
  });
}
