interface IconProps {
  className?: string;
}

/** Inline 24px stroke icons — no external icon dependency, so nothing to load at runtime. */
function base(className = "h-5 w-5") {
  return {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
}

export function ChartIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M3 3v18h18" />
      <path d="M7 15l3.5-4 3 2.5L20 7" />
    </svg>
  );
}

export function CalendarIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <rect x="3" y="5" width="18" height="16" rx="2.5" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}

export function UsersIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0M17 11.5a3 3 0 1 0-1.6-5.5M18 20a5.6 5.6 0 0 0-3-5" />
    </svg>
  );
}

export function CardIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
      <path d="M2.5 10h19M6 15h4" />
    </svg>
  );
}

export function PlugIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v5" />
    </svg>
  );
}

export function PenIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M4 20h4L20 8a2.8 2.8 0 0 0-4-4L4 16v4Z" />
      <path d="M14.5 5.5 18.5 9.5" />
    </svg>
  );
}

export function StackIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5M3 17.5l9 5 9-5" />
    </svg>
  );
}

export function SparkleIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

export function BellIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M18 16V11a6 6 0 1 0-12 0v5l-1.5 3h15L18 16ZM10 22h4" />
    </svg>
  );
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15M10 8l-4 4 4 4M6 12h11" />
    </svg>
  );
}

export function UploadIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M12 16V4M8 8l4-4 4 4M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16" />
    </svg>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
