import { useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "https://socioauto-production.up.railway.app/api/v1";

/**
 * Email/password sign-in that stores the access token for `api/client.ts`.
 *
 * Uses the OAuth2 password-grant form encoding the backend's /auth/token expects, so this
 * posts form data rather than JSON.
 */
export function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [registering, setRegistering] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = registering
        ? await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          })
        : await fetch(`${API_BASE}/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ username: email, password }),
          });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body?.detail ?? `Sign-in failed (${res.status})`);
      }
      localStorage.setItem("access_token", body.access_token);
      if (body.refresh_token) localStorage.setItem("refresh_token", body.refresh_token);
      onAuthenticated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 bg-white border rounded-lg p-6">
        <h1 className="text-xl font-bold">SocialMediaAI</h1>
        <p className="text-sm text-gray-600">
          {registering ? "Create an account" : "Sign in to the admin dashboard"}
        </p>

        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete={registering ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full px-4 py-2 rounded bg-indigo-600 text-white disabled:bg-gray-300"
        >
          {busy ? "Please wait…" : registering ? "Create account" : "Sign in"}
        </button>

        <button
          type="button"
          onClick={() => {
            setRegistering(!registering);
            setError(null);
          }}
          className="w-full text-sm text-indigo-600 underline"
        >
          {registering ? "I already have an account" : "Create an account instead"}
        </button>
      </form>
    </div>
  );
}
