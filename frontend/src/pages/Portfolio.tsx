import { useEffect, useState } from "react";
import { api, peso, type Band, type ClientSummary, type PortfolioStats } from "../api";
import {
  BAND_COLORS,
  BandBadge,
  Card,
  IconAlert,
  IconCheck,
  Spinner,
  titleCase,
} from "../components/ui";

const BANDS: Band[] = ["Healthy", "Coping", "Vulnerable"];

const KPI_ACCENT = {
  neutral: "text-slate-900",
  danger: "text-rose-600",
  positive: "text-emerald-600",
} as const;

function Kpi({
  label,
  value,
  sub,
  accent = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: keyof typeof KPI_ACCENT;
}) {
  return (
    <Card className="p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1.5 text-[26px] font-bold leading-none tabular-nums ${KPI_ACCENT[accent]}`}>
        {value}
      </div>
      {sub && <div className="mt-1.5 text-xs leading-snug text-slate-500">{sub}</div>}
    </Card>
  );
}

function BandDistribution({ stats }: { stats: PortfolioStats }) {
  return (
    <Card>
      <div className="mb-2 text-sm font-semibold">Health-band distribution</div>
      <div className="flex h-6 w-full overflow-hidden rounded-full">
        {BANDS.map((b) => (
          <div
            key={b}
            className={BAND_COLORS[b].bar}
            style={{ width: `${stats.band_pct[b]}%` }}
            title={`${b}: ${stats.band_counts[b]} (${stats.band_pct[b]}%)`}
          />
        ))}
      </div>
      <div className="mt-2 flex gap-4 text-xs text-slate-600">
        {BANDS.map((b) => (
          <span key={b} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${BAND_COLORS[b].bar}`} />
            {b}: {stats.band_counts[b]} ({stats.band_pct[b]}%)
          </span>
        ))}
      </div>
    </Card>
  );
}

export default function Portfolio({ onOpenClient }: { onOpenClient: (id: string) => void }) {
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [clients, setClients] = useState<ClientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.portfolio(), api.clients()])
      .then(([s, c]) => {
        setStats(s);
        setClients(c);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error)
    return (
      <Card className="border-rose-300 text-rose-700">
        Could not reach the backend ({error}). Is uvicorn running on port 8000?
      </Card>
    );
  if (!stats || !clients) return <Spinner label="Loading portfolio…" />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Total clients" value={String(stats.total_clients)} />
        <Kpi
          label="Vulnerable"
          value={`${stats.band_pct.Vulnerable}%`}
          sub={`${stats.band_counts.Vulnerable} clients below 40`}
          accent="danger"
        />
        <Kpi
          label="With resilience gap"
          value={`${stats.pct_with_resilience_gap}%`}
          sub="missing required protection"
          accent="danger"
        />
        <Kpi
          label="Uninsured exposure"
          value={peso(stats.aggregate_uninsured_exposure)}
          sub="cover value the portfolio lacks"
        />
        <Kpi
          label="Commission if gaps closed"
          value={`${peso(stats.projected_annual_commission)}/yr`}
          sub="the incentive to serve these clients"
          accent="positive"
        />
      </div>

      <BandDistribution stats={stats} />

      <Card className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-slate-200/80 px-5 py-3">
          <div className="text-sm font-semibold text-slate-800">Clients</div>
          <div className="text-xs text-slate-500">{clients.length} · sorted by FinHealth score</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200/80 bg-slate-50/80 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2.5">Client</th>
                <th className="px-5 py-2.5">Livelihood</th>
                <th className="px-5 py-2.5">Municipality</th>
                <th className="px-5 py-2.5">Hazard zone</th>
                <th className="px-5 py-2.5 text-right">FinHealth</th>
                <th className="px-5 py-2.5">Band</th>
                <th className="px-5 py-2.5">Gap</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr
                  key={c.client_id}
                  onClick={() => onOpenClient(c.client_id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onOpenClient(c.client_id);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  className="cursor-pointer border-b border-slate-100 outline-none transition-colors last:border-0 hover:bg-indigo-50/40 focus-visible:bg-indigo-50"
                >
                  <td className="px-5 py-2.5 font-medium text-slate-800">
                    {c.name}
                    <span className="ml-2 text-xs text-slate-400">{c.client_id}</span>
                  </td>
                  <td className="px-5 py-2.5 text-slate-600">{titleCase(c.livelihood)}</td>
                  <td className="px-5 py-2.5 text-slate-600">{c.municipality}</td>
                  <td className="px-5 py-2.5">
                    <span
                      className={
                        c.hazard_zone === "low_risk" ? "text-slate-500" : "font-medium text-rose-600"
                      }
                    >
                      {titleCase(c.hazard_zone)}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 text-right font-semibold tabular-nums text-slate-800">
                    {c.overall_score}
                  </td>
                  <td className="px-5 py-2.5">
                    <BandBadge band={c.band} />
                  </td>
                  <td className="px-5 py-2.5">
                    {c.has_resilience_gap ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600">
                        <IconAlert className="h-3.5 w-3.5" /> gap
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
                        <IconCheck className="h-3.5 w-3.5" /> covered
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
