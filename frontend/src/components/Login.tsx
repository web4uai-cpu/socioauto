import { useState } from "react";
import { Button } from "./ui/Button";
import { Field, Input } from "./ui/Input";
import { SparkleIcon } from "./ui/Icon";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "https://socioauto-production.up.railway.app/api/v1";

const HIGHLIGHTS = [
  "Eight AI agents from trend research to analytics",
  "Mandatory brand-safety review before anything publishes",
  "Photo, audio, and video posts across every major platform",
];

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
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-ink-700 via-ink-800 to-ink-900 p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -left-20 -top-24 h-96 w-96 rounded-full bg-brand-500 opacity-20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -right-16 h-96 w-96 rounded-full bg-series-3 opacity-10 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-lg font-black text-white shadow-glow">
            S
          </span>
          <span className="text-lg font-bold text-white">SocialMediaAI</span>
        </div>

        <div className="relative animate-fade-up">
          <h2 className="max-w-md text-4xl font-bold leading-tight tracking-tight text-white">
            Your entire social pipeline, run by agents.
          </h2>
          <ul className="mt-8 space-y-4">
            {HIGHLIGHTS.map((line) => (
              <li key={line} className="flex items-start gap-3 text-sm text-slate-300">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/20 text-brand-300">
                  <SparkleIcon className="h-3.5 w-3.5" />
                </span>
                {line}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">
          © {new Date().getFullYear()} SocialMediaAI — enterprise social automation
        </p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center bg-plane px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-sm animate-fade-up space-y-5">
          <div className="lg:hidden">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-lg font-black text-white shadow-glow">
              S
            </span>
          </div>

          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {registering ? "Create your account" : "Welcome back"}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {registering
                ? "Start creating and scheduling in minutes."
                : "Sign in to your workspace to continue."}
            </p>
          </div>

          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              required
              autoComplete="username"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              required
              autoComplete={registering ? "new-password" : "current-password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          {error && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              {error}
            </p>
          )}

          <Button type="submit" size="lg" loading={busy} className="w-full">
            {registering ? "Create account" : "Sign in"}
          </Button>

          <button
            type="button"
            onClick={() => {
              setRegistering(!registering);
              setError(null);
            }}
            className="w-full text-sm text-slate-500 transition-colors hover:text-brand-600"
          >
            {registering ? "I already have an account" : "Create an account instead"}
          </button>
        </form>
      </div>
    </div>
  );
}
