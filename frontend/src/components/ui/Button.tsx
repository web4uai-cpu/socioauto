import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

const VARIANT_STYLES: Record<Variant, string> = {
  primary:
    "bg-gradient-to-b from-brand-400 to-brand-600 text-white shadow-glow hover:from-brand-500 hover:to-brand-700 disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none",
  secondary:
    "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 hover:ring-slate-400 disabled:text-slate-400",
  ghost: "text-slate-600 hover:bg-slate-100 disabled:text-slate-300",
  danger:
    "bg-status-critical text-white hover:brightness-110 disabled:bg-slate-300",
  success:
    "bg-status-good text-white hover:brightness-110 disabled:bg-slate-300",
};

const SIZE_STYLES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-sm",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  loading?: boolean;
}

/** Primary action control: lifts on hover, depresses on click, dims while busy. */
export function Button({
  variant = "primary",
  size = "md",
  icon,
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`group relative inline-flex items-center justify-center gap-2 rounded-xl font-semibold
        transition-all duration-200 ease-out will-change-transform
        hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98]
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2
        disabled:cursor-not-allowed disabled:translate-y-0
        ${VARIANT_STYLES[variant]} ${SIZE_STYLES[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
