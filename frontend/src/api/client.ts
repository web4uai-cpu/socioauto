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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { ...authHeaders() } });
  if (!res.ok) throw await failure(res, "GET", path);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await failure(res, "POST", path);
  return res.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await failure(res, "PUT", path);
  return res.json() as Promise<T>;
}

/** Multipart upload — deliberately omits Content-Type so the browser sets the boundary. */
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (!res.ok) throw await failure(res, "POST", path);
  return res.json() as Promise<T>;
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
