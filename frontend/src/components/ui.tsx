// Small shared UI primitives. Colour is used only to encode band/severity.
import type { Band } from "../api";

// --- Icons (inline SVG, currentColor; never emoji as UI icons) --------------
type IconProps = { className?: string };

export function Logo({ className = "h-6 w-6" }: IconProps) {
  // Shield (protection) enclosing a heartbeat line (financial health).
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2.5 4.5 5.5v6c0 4.4 3.1 8.2 7.5 9.9 4.4-1.7 7.5-5.5 7.5-9.9v-6L12 2.5Z"
        fill="currentColor"
        opacity="0.14"
      />
      <path
        d="M12 2.5 4.5 5.5v6c0 4.4 3.1 8.2 7.5 9.9 4.4-1.7 7.5-5.5 7.5-9.9v-6L12 2.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M7.5 12.5h2l1.3-3 1.8 5 1.2-2h2.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconAlert({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3.5 22 20H2L12 3.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12 9.5v4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="17" r="1.05" fill="currentColor" />
    </svg>
  );
}

export function IconCheck({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12.5 10 17.5 19 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevronLeft({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M14.5 6 9 12l5.5 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconStorm({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7 15a4 4 0 0 1 .4-8A5 5 0 0 1 17 8.2 3.4 3.4 0 0 1 16.6 15"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12.5 13 10 17h3l-2.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export const BAND_COLORS: Record<Band, { bg: string; text: string; bar: string }> = {
  Healthy: { bg: "bg-emerald-100", text: "text-emerald-800", bar: "bg-emerald-500" },
  Coping: { bg: "bg-amber-100", text: "text-amber-800", bar: "bg-amber-500" },
  Vulnerable: { bg: "bg-rose-100", text: "text-rose-800", bar: "bg-rose-500" },
};

export function bandFor(score: number): Band {
  if (score >= 70) return "Healthy";
  if (score >= 40) return "Coping";
  return "Vulnerable";
}

export function BandBadge({ band }: { band: Band }) {
  const c = BAND_COLORS[band];
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${c.bg} ${c.text}`}>
      {band}
    </span>
  );
}

export function ScoreBar({ score }: { score: number }) {
  const c = BAND_COLORS[bandFor(score)];
  return (
    <div className="h-2 w-full rounded-full bg-slate-200">
      <div
        className={`h-2 rounded-full ${c.bar}`}
        style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
      />
    </div>
  );
}

export const TIER_STYLE: Record<
  "A" | "B" | "C",
  { bg: string; text: string; btn: string; label: string }
> = {
  A: {
    bg: "bg-emerald-100",
    text: "text-emerald-800",
    btn: "bg-emerald-600 hover:bg-emerald-700",
    label: "Tier A · Free government coverage",
  },
  B: {
    bg: "bg-sky-100",
    text: "text-sky-800",
    btn: "bg-sky-600 hover:bg-sky-700",
    label: "Tier B · Embedded microinsurance",
  },
  C: {
    bg: "bg-violet-100",
    text: "text-violet-800",
    btn: "bg-violet-600 hover:bg-violet-700",
    label: "Tier C · Targeted commercial",
  },
};

export function TierBadge({ tier }: { tier: "A" | "B" | "C" }) {
  const t = TIER_STYLE[tier];
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${t.bg} ${t.text}`}>
      {t.label}
    </span>
  );
}

export function SeverityChip({ level }: { level: "high" | "medium" }) {
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
        level === "high" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"
      }`}
    >
      {level}
    </span>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

const BUTTON_VARIANTS = {
  primary:
    "bg-indigo-600 text-white shadow-sm hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:hover:bg-indigo-600",
  subtle:
    "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 active:bg-slate-100 disabled:opacity-50",
} as const;

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_VARIANTS;
  size?: "sm" | "md";
}) {
  const sizing = size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm";
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition-colors disabled:cursor-not-allowed ${sizing} ${BUTTON_VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 p-8 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      {label ?? "Loading…"}
    </div>
  );
}

export const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
