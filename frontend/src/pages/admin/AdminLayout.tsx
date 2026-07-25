import { Outlet } from "react-router-dom";
import { AppShell } from "../../layouts/AppShell";

const NAV_ITEMS = [
  { to: "/admin/analytics", label: "Analytics" },
  { to: "/admin/content", label: "Content" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/billing", label: "Billing" },
  { to: "/admin/integrations", label: "Integrations" },
];

export function AdminLayout({ onSignOut }: { onSignOut: () => void }) {
  return (
    <AppShell title="Enterprise Admin" navItems={NAV_ITEMS} onSignOut={onSignOut}>
      <Outlet />
    </AppShell>
  );
}
