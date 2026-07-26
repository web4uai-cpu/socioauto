import { useEffect, useState } from "react";
import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { Login } from "./components/Login";
import { resolveRole } from "./api/client";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { AnalyticsPage } from "./pages/admin/AnalyticsPage";
import { ContentPage } from "./pages/admin/ContentPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { BillingPage } from "./pages/admin/BillingPage";
import { IntegrationsPage } from "./pages/admin/IntegrationsPage";
import { AiProviderPage } from "./pages/admin/AiProviderPage";
import { AppLayout } from "./pages/app/AppLayout";
import { ComposePage } from "./pages/app/ComposePage";
import { PostsPage } from "./pages/app/PostsPage";
import { PostDetailPage } from "./pages/app/PostDetailPage";
import { PersonalAnalyticsPage } from "./pages/app/PersonalAnalyticsPage";

type Role = "admin" | "user" | null;

/** Auth + role gate: routes to the enterprise admin console or the end-user console. */
export function App() {
  const [authenticated, setAuthenticated] = useState(
    () => localStorage.getItem("access_token") !== null,
  );
  const [role, setRole] = useState<Role>(null);

  useEffect(() => {
    if (!authenticated) {
      setRole(null);
      return;
    }
    resolveRole().then(setRole);
  }, [authenticated]);

  function signOut() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    sessionStorage.removeItem("role");
    setAuthenticated(false);
  }

  if (!authenticated) {
    return <Login onAuthenticated={() => setAuthenticated(true)} />;
  }

  if (role === null) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-plane">
        <span className="flex h-12 w-12 animate-pulse items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-xl font-black text-white shadow-glow">
          S
        </span>
        <p className="text-sm text-slate-400">Preparing your workspace…</p>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/admin/*"
          element={role === "admin" ? <AdminLayout onSignOut={signOut} /> : <Navigate to="/app/compose" replace />}
        >
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="content" element={<ContentPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="billing" element={<BillingPage />} />
          <Route path="ai" element={<AiProviderPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route index element={<Navigate to="analytics" replace />} />
        </Route>

        <Route path="/app/*" element={<AppLayout onSignOut={signOut} />}>
          <Route path="compose" element={<ComposePage />} />
          <Route path="posts" element={<PostsPage />} />
          <Route path="posts/:id" element={<PostDetailPage />} />
          <Route path="analytics" element={<PersonalAnalyticsPage />} />
          <Route index element={<Navigate to="compose" replace />} />
        </Route>

        <Route path="*" element={<Navigate to={role === "admin" ? "/admin" : "/app"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
