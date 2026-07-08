import { useEffect, useState } from "react";
import {
  api,
  peso,
  type HealthProfile,
  type RecommendationResponse,
} from "../api";
import {
  BandBadge,
  Card,
  ScoreBar,
  SeverityChip,
  Spinner,
  titleCase,
} from "../components/ui";

const DIMENSION_LABELS: Record<string, string> = {
  income_stability: "Income Stability",
  savings_liquidity: "Savings & Liquidity",
  debt_burden: "Debt Burden",
  resilience_protection: "Resilience & Protection",
};

export default function ClientDetail({
  clientId,
  onBack,
}: {
  clientId: string;
  onBack: () => void;
}) {
  const [profile, setProfile] = useState<HealthProfile | null>(null);
  const [recs, setRecs] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProfile(null);
    setRecs(null);
    Promise.all([api.client(clientId), api.recommendations(clientId)])
      .then(([p, r]) => {
        setProfile(p);
        setRecs(r);
      })
      .catch((e) => setError(String(e)));
  }, [clientId]);

  if (error) return <Card className="border-rose-300 text-rose-700">{error}</Card>;
  if (!profile) return <Spinner label="Loading client…" />;

  const divergent =
    profile.proxy_credit_signal - profile.overall_score >= 25 &&
    profile.band !== "Healthy";

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-sm font-medium text-sky-700 hover:underline">
        ← Back to portfolio
      </button>

      {/* Header: overall vs proxy credit signal, side by side */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">
              {profile.name}{" "}
              <span className="text-sm font-normal text-slate-400">{profile.client_id}</span>
            </h2>
            <div className="mt-1 text-sm text-slate-600">
              {titleCase(profile.livelihood)} · {profile.municipality} ·{" "}
              <span className={profile.hazard_zone === "low_risk" ? "" : "font-medium text-rose-600"}>
                {titleCase(profile.hazard_zone)} zone
              </span>{" "}
              · {profile.household_dependents} dependent(s)
            </div>
            <div className="mt-2 text-xs text-slate-500">
              Mean income {peso(profile.mean_monthly_income)}/mo · essentials{" "}
              {peso(profile.monthly_essential_expenses)}/mo · savings {peso(profile.liquid_savings)} ·
              debt service {peso(profile.monthly_debt_service)}/mo
            </div>
            {profile.imputed_fields.length > 0 && (
              <div className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                Imputed fields (not client-reported): {profile.imputed_fields.join(", ")}
              </div>
            )}
          </div>
          <div className="flex gap-6">
            <div className="text-center">
              <div className="text-xs font-medium uppercase text-slate-500">FinHealth score</div>
              <div className="text-4xl font-bold tabular-nums">{profile.overall_score}</div>
              <BandBadge band={profile.band} />
            </div>
            <div className="text-center">
              <div className="text-xs font-medium uppercase text-slate-500">Credit proxy*</div>
              <div className="text-4xl font-bold tabular-nums text-slate-400">
                {profile.proxy_credit_signal}
              </div>
              <BandBadge band={profile.proxy_credit_band} />
            </div>
          </div>
        </div>
        {divergent && (
          <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            <strong>Divergence:</strong> this client looks acceptable on a repayment-and-DSR
            credit proxy ({profile.proxy_credit_signal}) yet is{" "}
            {profile.band.toLowerCase()} on financial health ({profile.overall_score}) — thin
            savings and missing protection don't show up in a credit score until the shock hits.
          </div>
        )}
        <div className="mt-2 text-[11px] text-slate-400">
          *Credit proxy uses only repayment history and debt-service ratio — what a traditional
          screen sees. The FinHealth score is a transparent composite of the four dimensions below.
        </div>
      </Card>

      {/* Four dimension cards with drivers */}
      <div className="grid gap-3 md:grid-cols-2">
        {Object.entries(profile.dimensions).map(([key, dim]) => (
          <Card key={key}>
            <div className="flex items-center justify-between">
              <div className="font-semibold">
                {DIMENSION_LABELS[key] ?? titleCase(key)}
                {dim.ml_assisted && (
                  <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-indigo-700">
                    ML-assisted
                  </span>
                )}
              </div>
              <div className="text-2xl font-bold tabular-nums">{dim.score}</div>
            </div>
            <div className="mt-2">
              <ScoreBar score={dim.score} />
            </div>
            <ul className="mt-3 space-y-2">
              {dim.drivers.map((d, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium">{d.label}:</span>{" "}
                  <span className="text-slate-600">{d.detail}</span>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      {/* Resilience gap panel */}
      <Card>
        <div className="mb-2 font-semibold">Resilience gap — required protection not held</div>
        {profile.resilience_gap.length === 0 ? (
          <div className="text-sm text-emerald-700">
            All exposure-required protection is in place.
          </div>
        ) : (
          <ul className="space-y-2">
            {profile.resilience_gap.map((g) => (
              <li key={g.type} className="flex items-start gap-2 text-sm">
                <SeverityChip level={g.severity_label} />
                <span>
                  <span className="font-semibold">{titleCase(g.type)}</span>
                  <span className="text-slate-600"> — {g.reason}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {profile.insurance_held.length > 0 && (
          <div className="mt-3 text-xs text-slate-500">
            Currently held: {profile.insurance_held.map(titleCase).join(", ")}
          </div>
        )}
      </Card>

      {/* Recommendations */}
      <Card>
        <div className="mb-1 font-semibold">Protection recommendations</div>
        {recs ? (
          <>
            <div className="mb-3 text-xs text-slate-500">
              Disposable income: {peso(recs.disposable_income)}/mo · {recs.note}
            </div>
            <div className="space-y-3">
              {recs.recommendations.map((r, i) =>
                r.status === "recommended" && r.product ? (
                  <div key={i} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-semibold">
                        {r.product.name}{" "}
                        <span className="text-xs font-normal text-slate-500">
                          {r.product.provider} · {titleCase(r.gap_type)} ·{" "}
                          {peso(r.product.coverage_amount)} cover
                        </span>
                      </div>
                      <SeverityChip level={r.severity_label} />
                    </div>
                    <p className="mt-1.5 text-sm text-slate-600">{r.rationale}</p>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs">
                      <span className="font-medium">
                        {peso(r.product.monthly_premium)}/mo ={" "}
                        {r.premium_pct_of_disposable}% of disposable income
                      </span>
                      <span className="text-slate-500">
                        Projected commission to institution:{" "}
                        {peso(r.projected_annual_commission ?? 0)}/yr
                      </span>
                    </div>
                  </div>
                ) : (
                  <div key={i} className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-amber-900">
                        {titleCase(r.gap_type)} — protection gap, no affordable product
                      </div>
                      <SeverityChip level={r.severity_label} />
                    </div>
                    <p className="mt-1.5 text-sm text-amber-800">{r.rationale}</p>
                  </div>
                ),
              )}
              {recs.recommendations.length === 0 && (
                <div className="text-sm text-emerald-700">No gaps — nothing to recommend.</div>
              )}
            </div>
          </>
        ) : (
          <Spinner label="Loading recommendations…" />
        )}
      </Card>
    </div>
  );
}
