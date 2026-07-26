import { Outlet, useLocation } from "react-router-dom";
import { AppShell, type NavItem } from "../../layouts/AppShell";
import {
  CalendarIcon,
  CardIcon,
  ChartIcon,
  PlugIcon,
  SparkleIcon,
  UsersIcon,
} from "../../components/ui/Icon";

const NAV_ITEMS: NavItem[] = [
  { to: "/admin/analytics", label: "Analytics", icon: <ChartIcon className="h-5 w-5" /> },
  { to: "/admin/content", label: "Content", icon: <CalendarIcon className="h-5 w-5" /> },
  { to: "/admin/users", label: "Users", icon: <UsersIcon className="h-5 w-5" /> },
  { to: "/admin/billing", label: "Billing", icon: <CardIcon className="h-5 w-5" /> },
  { to: "/admin/ai", label: "AI Provider", icon: <SparkleIcon className="h-5 w-5" /> },
  { to: "/admin/integrations", label: "Integrations", icon: <PlugIcon className="h-5 w-5" /> },
];

const TITLES: Record<string, { title: string; subtitle: string }> = {
  analytics: { title: "Analytics", subtitle: "Platform-wide performance and pipeline health" },
  content: { title: "Content", subtitle: "Calendar and human-in-the-loop review queue" },
  users: { title: "Users", subtitle: "Accounts, roles, and access" },
  billing: { title: "Billing", subtitle: "Subscriptions, invoices, and revenue" },
  ai: { title: "AI Provider", subtitle: "Pick the best model for each job the agents do" },
  integrations: { title: "Integrations", subtitle: "API keys and third-party connections" },
};

export function AdminLayout({ onSignOut }: { onSignOut: () => void }) {
  const { pathname } = useLocation();
  const section = pathname.split("/")[2] ?? "analytics";
  const meta = TITLES[section] ?? TITLES.analytics;

  return (
    <AppShell
      kind="Enterprise Admin"
      title={meta.title}
      subtitle={meta.subtitle}
      navItems={NAV_ITEMS}
      onSignOut={onSignOut}
    >
      <Outlet />
    </AppShell>
  );
}
