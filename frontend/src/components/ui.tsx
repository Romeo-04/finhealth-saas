// Small shared UI primitives. Colour is used only to encode band/severity.
import type { Band } from "../api";

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
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-8 text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
      {label ?? "Loading…"}
    </div>
  );
}

export const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
