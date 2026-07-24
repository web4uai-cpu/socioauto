import { useEffect, useState } from "react";
import { apiGet } from "../api/client";

interface AppUser {
  id: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "editor" | "viewer";
  is_active: boolean;
}

/** Admin: list, search, and manage user roles/status. Backed by GET /api/v1/admin/users (TODO). */
export function UserManagementTable() {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<AppUser[]>("/admin/users")
      .then(setUsers)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="text-lg font-semibold mb-3">User Management</h2>
      {error && <p className="text-red-600 text-sm mb-2">Failed to load users: {error}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-gray-200">
            <th className="py-2">Email</th>
            <th>Name</th>
            <th>Role</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-gray-100">
              <td className="py-2">{u.email}</td>
              <td>{u.full_name ?? "—"}</td>
              <td className="capitalize">{u.role}</td>
              <td>{u.is_active ? "Active" : "Suspended"}</td>
            </tr>
          ))}
          {users.length === 0 && !error && (
            <tr>
              <td colSpan={4} className="py-4 text-center text-gray-400">
                No users yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
