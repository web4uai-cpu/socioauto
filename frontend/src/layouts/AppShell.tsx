import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
}

interface AppShellProps {
  title: string;
  navItems: NavItem[];
  onSignOut: () => void;
  children: ReactNode;
}

/** Sidebar + topbar shell shared by the admin console and the end-user console. */
export function AppShell({ title, navItems, onSignOut, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="flex">
        <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white px-4 py-6 sm:block">
          <div className="mb-8 px-2 text-lg font-bold text-brand-600">SocialMediaAI</div>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="flex-1">
          <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
            <h1 className="text-base font-semibold">{title}</h1>
            <button
              type="button"
              onClick={onSignOut}
              className="text-sm text-gray-500 underline-offset-2 hover:text-gray-800 hover:underline"
            >
              Sign out
            </button>
          </header>
          <main className="mx-auto max-w-6xl space-y-6 p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
