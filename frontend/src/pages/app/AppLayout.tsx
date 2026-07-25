import { Outlet } from "react-router-dom";
import { AppShell } from "../../layouts/AppShell";

const NAV_ITEMS = [
  { to: "/app/compose", label: "Compose" },
  { to: "/app/posts", label: "My posts" },
  { to: "/app/analytics", label: "Analytics" },
];

export function AppLayout({ onSignOut }: { onSignOut: () => void }) {
  return (
    <AppShell title="Create & Post" navItems={NAV_ITEMS} onSignOut={onSignOut}>
      <Outlet />
    </AppShell>
  );
}
