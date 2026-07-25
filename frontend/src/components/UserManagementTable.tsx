import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { UsersIcon } from "./ui/Icon";

interface AppUser {
  id: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "editor" | "viewer";
  is_active: boolean;
}

const ROLE_STYLES: Record<AppUser["role"], string> = {
  owner: "bg-violet-50 text-violet-700 ring-violet-200",
  admin: "bg-brand-50 text-brand-700 ring-brand-200",
  editor: "bg-amber-50 text-amber-700 ring-amber-200",
  viewer: "bg-slate-100 text-slate-600 ring-slate-200",
};

/** Admin: list, search, and manage user roles/status. Backed by GET /api/v1/admin/users. */
export function UserManagementTable() {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    apiGet<AppUser[]>("/admin/users")
      .then(setUsers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = users.filter(
    (u) =>
      u.email.toLowerCase().includes(query.toLowerCase()) ||
      (u.full_name ?? "").toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <Card>
      <CardHeader
        title="User management"
        subtitle={`${users.length} account${users.length === 1 ? "" : "s"} in this workspace`}
        icon={<UsersIcon className="h-5 w-5" />}
        action={
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter users…"
            className="w-44 rounded-xl bg-slate-100 px-3 py-2 text-sm outline-none transition-all
              placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-brand-500"
          />
        }
      />
      <CardBody className="p-0">
        {error && (
          <p role="alert" className="m-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            Failed to load users: {error}
          </p>
        )}

        {loading ? (
          <div className="space-y-2 p-5">
            <div className="skeleton h-10 w-full" />
            <div className="skeleton h-10 w-full" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left">
                  <th className="px-6 py-3 font-semibold text-slate-500">User</th>
                  <th className="px-6 py-3 font-semibold text-slate-500">Name</th>
                  <th className="px-6 py-3 font-semibold text-slate-500">Role</th>
                  <th className="px-6 py-3 font-semibold text-slate-500">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-slate-50 transition-colors last:border-0 hover:bg-brand-50/40"
                  >
                    <td className="px-6 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-xs font-semibold uppercase text-white">
                          {u.email.slice(0, 2)}
                        </span>
                        <span className="font-medium text-slate-900">{u.email}</span>
                      </div>
                    </td>
                    <td className="px-6 py-3.5 text-slate-600">{u.full_name ?? "—"}</td>
                    <td className="px-6 py-3.5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize
                          ring-1 ring-inset ${ROLE_STYLES[u.role]}`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="px-6 py-3.5">
                      <Badge tone={u.is_active ? "active" : "canceled"}>
                        {u.is_active ? "Active" : "Suspended"}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && !error && (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-400">
                      {users.length === 0 ? "No users yet" : "No users match that filter"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
