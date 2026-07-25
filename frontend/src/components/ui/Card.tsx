import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Adds a hover lift — use for cards that are clickable or scannable in a grid. */
  interactive?: boolean;
  /** Colored top hairline, e.g. "from-series-1 to-brand-400". */
  accent?: string;
}

export function Card({ interactive, accent, className = "", children, ...props }: CardProps) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl bg-surface shadow-card ring-1 ring-slate-900/[0.06]
        transition-all duration-300 ease-out
        ${interactive ? "hover:-translate-y-1 hover:shadow-lift hover:ring-brand-200" : ""}
        ${className}`}
      {...props}
    >
      {accent && <div className={`h-1 w-full bg-gradient-to-r ${accent}`} />}
      {children}
    </div>
  );
}

interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon,
  className = "",
  ...props
}: CardHeaderProps) {
  return (
    <div
      className={`flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5 ${className}`}
      {...props}
    >
      <div className="flex min-w-0 items-center gap-3">
        {icon && (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold tracking-tight text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`px-6 py-5 ${className}`} {...props} />;
}
