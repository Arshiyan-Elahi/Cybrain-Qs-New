const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'cybrain-qs.token';

/** Thrown for any non-2xx response, carrying the status so callers can branch. */
export class ApiError extends Error {
  // Declared explicitly rather than as a parameter property, which
  // `erasableSyntaxOnly` disallows.
  status: number;
  details: Record<string, unknown>;

  constructor(status: number, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable; the session still works until reload.
  }
}

async function toError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  let details: Record<string, unknown> = {};
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') {
      detail = body.detail;
    } else if (Array.isArray(body?.detail)) {
      // FastAPI validation errors arrive as a list of field problems.
      detail = body.detail.map((e: { msg?: string }) => e.msg).filter(Boolean).join(', ');
    } else if (typeof body?.error?.message === 'string') {
      // Cybrain QS domain errors use { error: { code, message, details } }.
      detail = body.error.message;
      if (body.error.details && typeof body.error.details === 'object') {
        details = body.error.details as Record<string, unknown>;
      }
    }
  } catch {
    // Body was not JSON — keep the status text.
  }
  return new ApiError(response.status, detail, details);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Send as multipart instead of JSON. */
  formData?: FormData;
  signal?: AbortSignal;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, signal } = options;

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    signal,
    cache: 'no-store',
  });

  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
