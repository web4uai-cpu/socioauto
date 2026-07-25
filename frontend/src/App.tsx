import { useState } from "react";
import { Login } from "./components/Login";
import { AdminDashboard } from "./pages/AdminDashboard";

/** Auth gate: show the dashboard once a token is stored, otherwise the sign-in form. */
export function App() {
  const [authenticated, setAuthenticated] = useState(
    () => localStorage.getItem("access_token") !== null,
  );

  if (!authenticated) {
    return <Login onAuthenticated={() => setAuthenticated(true)} />;
  }

  function signOut() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setAuthenticated(false);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex justify-end p-4">
        <button type="button" onClick={signOut} className="text-sm text-gray-600 underline">
          Sign out
        </button>
      </header>
      <AdminDashboard />
    </div>
  );
}
