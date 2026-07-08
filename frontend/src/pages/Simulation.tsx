import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type SimulationResult } from "../api";
import { Button, Card, IconStorm, Spinner } from "../components/ui";

export default function Simulation() {
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = () => {
    setRunning(true);
    setError(null);
    api
      .simulate()
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setRunning(false));
  };

  const chartData =
    result &&
    result.cohorts.protected.trajectory.map((q, i) => ({
      quarter: q.quarter,
      protected: q.mean_score,
      unprotected: result.cohorts.unprotected.trajectory[i].mean_score,
    }));

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-bold">Longitudinal outcome simulation</h2>
        <p className="mt-1 text-sm text-slate-600">
          Runs 4 quarters over the real scoring engine. At Q3 a simulated typhoon hits every
          client in a typhoon/flood zone, cutting income and draining savings. Clients holding
          calamity or crop cover absorb a far smaller hit and recover; uninsured clients drop
          sharply and stay low. This is the outcome feedback loop most FSPs never run.
        </p>
        <Button onClick={run} disabled={running} className="mt-4">
          {running ? "Running…" : result ? "Re-run simulation" : "Run 4-quarter shock simulation"}
        </Button>
        {error && <div className="mt-2 text-sm text-rose-700">{error}</div>}
      </Card>

      {running && <Spinner label="Scoring all clients across 4 quarters…" />}

      {result && chartData && (
        <>
          <Card>
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
              <div className="font-semibold">
                Mean FinHealth score — protected vs unprotected ({result.affected_clients} clients
                in affected zones)
              </div>
              <div className="text-xs text-slate-500">
                protected n={result.cohorts.protected.size} · unprotected n=
                {result.cohorts.unprotected.size}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 12, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="quarter"
                  tick={{ fontSize: 12, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={{ stroke: "#cbd5e1" }}
                />
                <YAxis
                  domain={[0, 80]}
                  tick={{ fontSize: 12, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <ReferenceLine
                  x={result.shock_quarter}
                  stroke="#e11d48"
                  strokeDasharray="4 4"
                  label={{ value: "Typhoon shock", position: "top", fill: "#e11d48", fontSize: 12 }}
                />
                <Line
                  type="monotone"
                  dataKey="protected"
                  name="Protected (holds calamity/crop cover)"
                  stroke="#059669"
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="unprotected"
                  name="Unprotected"
                  stroke="#e11d48"
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            {(["protected", "unprotected"] as const).map((cohort) => (
              <Card key={cohort}>
                <div className="mb-2 font-semibold">
                  {cohort === "protected" ? "Protected cohort" : "Unprotected cohort"} — band
                  counts by quarter
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-slate-500">
                      <th className="py-1">Quarter</th>
                      <th className="py-1 text-emerald-700">Healthy</th>
                      <th className="py-1 text-amber-700">Coping</th>
                      <th className="py-1 text-rose-700">Vulnerable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.cohorts[cohort].trajectory.map((q) => (
                      <tr key={q.quarter} className={q.shock ? "bg-rose-50" : ""}>
                        <td className="py-1 font-medium">
                          <span className="inline-flex items-center gap-1">
                            {q.quarter}
                            {q.shock && <IconStorm className="h-3.5 w-3.5 text-rose-500" />}
                          </span>
                        </td>
                        <td className="py-1 tabular-nums">{q.band_distribution.Healthy}</td>
                        <td className="py-1 tabular-nums">{q.band_distribution.Coping}</td>
                        <td className="py-1 tabular-nums">{q.band_distribution.Vulnerable}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
