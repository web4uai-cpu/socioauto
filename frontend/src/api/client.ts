// Thin fetch wrapper for the v1 API. Reads the bearer token from localStorage (set at login).
// Override the host per-environment with VITE_API_BASE_URL (see frontend/.env.example);
// the fallback points at the deployed Railway backend.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "https://socioauto-production.up.railway.app/api/v1";

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Surface the API's error detail rather than a bare status code, so forms can show it. */
async function failure(res: Response, method: string, path: string): Promise<Error> {
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    // Non-JSON error body — fall back to the status line.
  }
  return new Error(detail || `${method} ${path} failed: ${res.status}`);
}

/** Drop credentials and return to the login screen. Used when the session cannot be revived. */
function endSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  sessionStorage.removeItem("role");
  // A full reload re-runs App's auth gate, which renders <Login/>. Beats leaving the user on
  // a dead page whose every request 401s.
  window.location.reload();
}

// Access tokens live 15 minutes, so a 401 mid-session is expected rather than exceptional.
// One refresh runs at a time: a page firing several requests in parallel would otherwise
// send several refreshes, and each rotates the refresh token, invalidating the others.
let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refresh_token = localStorage.getItem("refresh_token");
  if (!refresh_token) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) return false;
    const body = await res.json();
    if (!body?.access_token) return false;
    localStorage.setItem("access_token", body.access_token);
    if (body.refresh_token) localStorage.setItem("refresh_token", body.refresh_token);
    return true;
  } catch {
    return false;
  }
}

/**
 * Issue a request, transparently renewing an expired access token once.
 *
 * `build` is called again for the retry so the retried request carries the *new* token —
 * headers are captured at call time, not request time.
 */
async function request<T>(method: string, path: string, build: () => RequestInit): Promise<T> {
  let res = await fetch(`${API_BASE}${path}`, build());

  if (res.status === 401 && localStorage.getItem("refresh_token")) {
    refreshing = refreshing ?? refreshSession().finally(() => (refreshing = null));
    if (await refreshing) {
      res = await fetch(`${API_BASE}${path}`, build());
    }
  }

  if (res.status === 401) {
    // The session is genuinely over — bounce to login rather than showing an empty page.
    endSession();
    throw await failure(res, method, path);
  }

  if (!res.ok) throw await failure(res, method, path);
  return res.json() as Promise<T>;
}

/** Request body shared by the JSON verbs. */
function jsonInit(method: string, body?: unknown): () => RequestInit {
  return () => ({
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path, () => ({ headers: { ...authHeaders() } }));
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, jsonInit("POST", body));
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PUT", path, jsonInit("PUT", body));
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PATCH", path, jsonInit("PATCH", body));
}

/** Multipart upload — deliberately omits Content-Type so the browser sets the boundary. */
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return request<T>("POST", path, () => ({
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  }));
}

/** Root the backend serves media/static assets from, for resolving relative /media/* URLs. */
export const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

/** Best-effort admin check: an admin-only endpoint succeeds only for admins. Cached per session. */
export async function resolveRole(): Promise<"admin" | "user"> {
  const cached = sessionStorage.getItem("role");
  if (cached === "admin" || cached === "user") return cached;
  try {
    await apiGet("/admin/users");
    sessionStorage.setItem("role", "admin");
    return "admin";
  } catch {
    sessionStorage.setItem("role", "user");
    return "user";
  }
}
