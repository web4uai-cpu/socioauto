import { Outlet, useLocation } from "react-router-dom";
import { AppShell, type NavItem } from "../../layouts/AppShell";
import { ChartIcon, PenIcon, StackIcon } from "../../components/ui/Icon";

const NAV_ITEMS: NavItem[] = [
  { to: "/app/compose", label: "Compose", icon: <PenIcon className="h-5 w-5" /> },
  { to: "/app/posts", label: "My posts", icon: <StackIcon className="h-5 w-5" /> },
  { to: "/app/analytics", label: "Analytics", icon: <ChartIcon className="h-5 w-5" /> },
];

const TITLES: Record<string, { title: string; subtitle: string }> = {
  compose: { title: "Compose", subtitle: "Write it yourself or generate it — then add photo, audio, or video" },
  posts: { title: "My posts", subtitle: "Everything you've created, and where it stands" },
  analytics: { title: "Analytics", subtitle: "How your posts are performing" },
};

export function AppLayout({ onSignOut }: { onSignOut: () => void }) {
  const { pathname } = useLocation();
  const section = pathname.split("/")[2] ?? "compose";
  const meta = TITLES[section] ?? TITLES.compose;

  return (
    <AppShell
      kind="Creator Studio"
      title={meta.title}
      subtitle={meta.subtitle}
      navItems={NAV_ITEMS}
      onSignOut={onSignOut}
    >
      <Outlet />
    </AppShell>
  );
}
