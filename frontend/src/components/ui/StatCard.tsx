import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: number | string;
  /** Small qualifier under the value, e.g. "across 4 platforms". */
  hint?: string;
  icon?: ReactNode;
  /** Tailwind gradient stops for the icon chip, e.g. "from-brand-400 to-brand-600". */
  tone?: string;
  loading?: boolean;
}

/**
 * KPI tile. The value is the hero — it carries text ink, not a series color, and the
 * colored chip beside it carries the identity (see the data-viz color rules).
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "from-brand-400 to-brand-600",
  loading = false,
}: StatCardProps) {
  return (
    <div
      className="group relative overflow-hidden rounded-2xl bg-surface p-5 shadow-card ring-1 ring-slate-900/[0.06]
        transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-lift"
    >
      {/* Ambient wash that warms on hover — decorative only. */}
      <div
        className={`pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-gradient-to-br ${tone}
          opacity-[0.07] blur-2xl transition-opacity duration-300 group-hover:opacity-20`}
      />
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        {icon && (
          <span
            className={`flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br ${tone}
              text-white shadow-sm transition-transform duration-300 group-hover:scale-110`}
          >
            {icon}
          </span>
        )}
      </div>
      {loading ? (
        <div className="skeleton mt-3 h-9 w-20" />
      ) : (
        <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">{value}</p>
      )}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
