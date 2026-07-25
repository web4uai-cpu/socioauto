import type { ReactNode } from "react";

export const STATUS_BADGE_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_moderation: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  rejected: "bg-red-100 text-red-800",
  scheduled: "bg-indigo-100 text-indigo-800",
  published: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export function Badge({ children, tone = "gray" }: { children: ReactNode; tone?: string }) {
  const style = STATUS_BADGE_STYLES[tone] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {children}
    </span>
  );
}
