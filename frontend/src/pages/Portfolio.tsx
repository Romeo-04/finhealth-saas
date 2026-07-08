import { useEffect, useState } from "react";
import { api, peso, type Band, type ClientSummary, type PortfolioStats } from "../api";
import { BAND_COLORS, BandBadge, Card, Spinner, titleCase } from "../components/ui";

const BANDS: Band[] = ["Healthy", "Coping", "Vulnerable"];

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
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
        />
        <Kpi
          label="With resilience gap"
          value={`${stats.pct_with_resilience_gap}%`}
          sub="missing required protection"
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
        />
      </div>

      <BandDistribution stats={stats} />

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3">Client</th>
              <th className="px-4 py-3">Livelihood</th>
              <th className="px-4 py-3">Municipality</th>
              <th className="px-4 py-3">Hazard zone</th>
              <th className="px-4 py-3 text-right">FinHealth</th>
              <th className="px-4 py-3">Band</th>
              <th className="px-4 py-3">Gap</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr
                key={c.client_id}
                onClick={() => onOpenClient(c.client_id)}
                className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-4 py-2.5 font-medium">
                  {c.name}
                  <span className="ml-2 text-xs text-slate-400">{c.client_id}</span>
                </td>
                <td className="px-4 py-2.5">{titleCase(c.livelihood)}</td>
                <td className="px-4 py-2.5">{c.municipality}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={
                      c.hazard_zone === "low_risk" ? "text-slate-500" : "font-medium text-rose-600"
                    }
                  >
                    {titleCase(c.hazard_zone)}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">
                  {c.overall_score}
                </td>
                <td className="px-4 py-2.5">
                  <BandBadge band={c.band} />
                </td>
                <td className="px-4 py-2.5">
                  {c.has_resilience_gap ? (
                    <span className="text-xs font-semibold text-rose-600">⚠ gap</span>
                  ) : (
                    <span className="text-xs text-emerald-600">covered</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
