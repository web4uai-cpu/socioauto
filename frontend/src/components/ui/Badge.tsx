import type { ReactNode } from "react";

/**
 * Status chips. Each pairs a colored dot with a text label — status is never carried by
 * color alone (see the data-viz status rules).
 */
export const STATUS_BADGE_STYLES: Record<string, { chip: string; dot: string }> = {
  draft: { chip: "bg-slate-100 text-slate-600 ring-slate-200", dot: "bg-slate-400" },
  pending_moderation: { chip: "bg-amber-50 text-amber-700 ring-amber-200", dot: "bg-status-warning" },
  approved: { chip: "bg-brand-50 text-brand-700 ring-brand-200", dot: "bg-brand-500" },
  rejected: { chip: "bg-red-50 text-red-700 ring-red-200", dot: "bg-status-critical" },
  scheduled: { chip: "bg-violet-50 text-violet-700 ring-violet-200", dot: "bg-violet-500" },
  published: { chip: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-status-good" },
  failed: { chip: "bg-red-50 text-red-700 ring-red-200", dot: "bg-status-critical" },
  active: { chip: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-status-good" },
  paid: { chip: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-status-good" },
  open: { chip: "bg-amber-50 text-amber-700 ring-amber-200", dot: "bg-status-warning" },
  past_due: { chip: "bg-red-50 text-red-700 ring-red-200", dot: "bg-status-critical" },
  canceled: { chip: "bg-slate-100 text-slate-600 ring-slate-200", dot: "bg-slate-400" },
  trialing: { chip: "bg-brand-50 text-brand-700 ring-brand-200", dot: "bg-brand-500" },
};

const FALLBACK = { chip: "bg-slate-100 text-slate-600 ring-slate-200", dot: "bg-slate-400" };

export function Badge({
  children,
  tone = "draft",
  dot = true,
}: {
  children: ReactNode;
  tone?: string;
  dot?: boolean;
}) {
  const style = STATUS_BADGE_STYLES[tone] ?? FALLBACK;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium
        ring-1 ring-inset ${style.chip}`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />}
      {children}
    </span>
  );
}
