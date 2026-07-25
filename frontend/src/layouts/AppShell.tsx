import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { BellIcon, LogoutIcon, MenuIcon, SearchIcon } from "../components/ui/Icon";

export interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

interface AppShellProps {
  /** Console name shown under the wordmark, e.g. "Enterprise Admin". */
  kind: string;
  title: string;
  subtitle?: string;
  navItems: NavItem[];
  onSignOut: () => void;
  children: ReactNode;
}

/** Shared chrome: colored sidebar, sticky header, wide content plane. */
export function AppShell({
  kind,
  title,
  subtitle,
  navItems,
  onSignOut,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const nav = (
    <nav className="space-y-1">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={() => setMobileNavOpen(false)}
          className={({ isActive }) =>
            `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium
             transition-all duration-200 ${
               isActive
                 ? "bg-white/10 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.08)]"
                 : "text-slate-400 hover:bg-white/5 hover:text-white"
             }`
          }
        >
          {({ isActive }) => (
            <>
              {/* Active rail — the one saturated accent in the sidebar. */}
              <span
                className={`absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full
                  bg-gradient-to-b from-brand-300 to-brand-500 transition-all duration-300
                  ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-40"}`}
              />
              <span
                className={`transition-transform duration-200 group-hover:scale-110 ${
                  isActive ? "text-brand-300" : ""
                }`}
              >
                {item.icon}
              </span>
              {item.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-plane">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-gradient-to-b from-ink-700 via-ink-800 to-ink-900
          px-4 py-6 transition-transform duration-300 lg:translate-x-0
          ${mobileNavOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="mb-8 flex items-center gap-3 px-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-lg font-black text-white shadow-glow">
            S
          </span>
          <div className="leading-tight">
            <div className="text-sm font-bold text-white">SocialMediaAI</div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-brand-300">
              {kind}
            </div>
          </div>
        </div>

        {nav}

        <div className="absolute inset-x-4 bottom-6">
          <button
            type="button"
            onClick={onSignOut}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium
              text-slate-400 transition-colors duration-200 hover:bg-white/5 hover:text-white"
          >
            <LogoutIcon className="h-5 w-5" />
            Sign out
          </button>
        </div>
      </aside>

      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink-900/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* Content plane */}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
          <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-5 py-3.5 sm:px-8">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 lg:hidden"
            >
              <MenuIcon className="h-5 w-5" />
            </button>

            <div className="min-w-0 flex-1">
              <h1 className="truncate text-[15px] font-semibold tracking-tight text-slate-900">
                {title}
              </h1>
              {subtitle && <p className="truncate text-xs text-slate-500">{subtitle}</p>}
            </div>

            <div className="relative hidden md:block">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Search…"
                className="w-56 rounded-xl bg-slate-100 py-2 pl-9 pr-3 text-sm outline-none
                  transition-all duration-200 placeholder:text-slate-400
                  focus:w-72 focus:bg-white focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <button
              type="button"
              aria-label="Notifications"
              className="relative rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
            >
              <BellIcon className="h-5 w-5" />
              <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-status-critical ring-2 ring-white" />
            </button>

            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-sm font-semibold text-white">
              A
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-[1600px] space-y-6 px-5 py-8 sm:px-8">{children}</main>
      </div>
    </div>
  );
}
