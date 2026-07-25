import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const FIELD = `w-full rounded-xl bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400
  ring-1 ring-inset ring-slate-300 outline-none transition-all duration-200
  hover:ring-slate-400 focus:ring-2 focus:ring-brand-500 focus:shadow-[0_0_0_4px_rgb(42_120_214/0.10)]
  disabled:bg-slate-50 disabled:text-slate-400`;

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${FIELD} ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${FIELD} resize-y leading-relaxed ${className}`} {...props} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${FIELD} ${className}`} {...props} />;
}

export function Field({
  label,
  hint,
  htmlFor,
  children,
  action,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-sm font-medium text-slate-700">
          {label}
        </label>
        {action}
      </div>
      {children}
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
