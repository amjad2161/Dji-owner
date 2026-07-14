/**
 * SkyCore auth helper — one place for the signed token, API base, and WS base.
 *
 * The backend verifies credentials SERVER-SIDE (POST /api/login) and returns a
 * signed token. The client stores it and attaches it to every REST call
 * (Authorization: Bearer) and every WebSocket (?token=, since browsers cannot set
 * WS request headers). No credential map ships in the client bundle.
 */

const TOKEN_KEY = 'skycore_token';
const USER_KEY = 'skycore_user';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function decodeToken(token: string): { sub?: string; role?: string; exp?: number } | null {
  try {
    const payload = token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** A locally-valid token has a future exp. (The server still verifies the signature.) */
export function tokenValid(token: string): boolean {
  const d = decodeToken(token);
  return !!(d && typeof d.exp === 'number' && d.exp * 1000 > Date.now());
}

export function setSession(token: string, username: string, role: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify({ username, role }));
}

export function getUser(): { username: string; role: string } | null {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch {
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/** REST base: same-origin under the unified server; dev talks to the backend on :8080. */
export function apiBase(): string {
  return import.meta.env.DEV ? `${window.location.protocol}//${window.location.hostname}:8080` : '';
}

/** WebSocket base: same-origin (wss under https) in prod; dev backend on :8080. */
export function wsBase(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.DEV ? `${window.location.hostname}:8080` : window.location.host;
  return `${proto}//${host}`;
}

/** Build a WS URL carrying the auth token as a query param. */
export function wsUrl(path: string): string {
  const t = getToken();
  return `${wsBase()}${path}${t ? `?token=${encodeURIComponent(t)}` : ''}`;
}

/** Authenticated GET returning parsed JSON (throws on non-2xx). */
export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

/** Log in against the backend; returns the signed token + role. Throws on failure. */
export async function login(username: string, password: string): Promise<{ token: string; role: string }> {
  const res = await fetch(`${apiBase()}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('invalid credentials');
  const data = await res.json();
  return { token: data.token as string, role: (data.role as string) || 'viewer' };
}
