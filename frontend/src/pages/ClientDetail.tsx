import { useEffect, useState } from "react";
import {
  api,
  peso,
  type HealthProfile,
  type Recommendation,
  type RecommendationResponse,
  type Tier,
} from "../api";
import {
  BandBadge,
  Card,
  ScoreBar,
  SeverityChip,
  Spinner,
  TIER_STYLE,
  TierBadge,
  titleCase,
} from "../components/ui";

// Fixed display order for the five revised-architecture dimensions.
const DIMENSION_ORDER = ["spend", "save", "borrow", "plan", "resilience"];
const DIMENSION_LABELS: Record<string, string> = {
  spend: "Spend",
  save: "Save",
  borrow: "Borrow",
  plan: "Plan",
  resilience: "Resilience",
};

const TIER_ACTION: Record<Tier, string> = {
  A: "Enroll in PCIC",
  B: "Activate coverage",
  C: "Initiate application",
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

  const orderedDims = DIMENSION_ORDER.filter((k) => k in profile.dimensions).map(
    (k) => [k, profile.dimensions[k]] as const,
  );

  const recommended = recs?.recommendations.filter((r) => r.status === "recommended") ?? [];
  const unaffordable = recs?.recommendations.filter((r) => r.status !== "recommended") ?? [];
  const tiers: Tier[] = ["A", "B", "C"];

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
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-600">
              <span>{titleCase(profile.livelihood)}</span>
              <span>· {profile.municipality} ·</span>
              <span className={profile.hazard_zone === "low_risk" ? "" : "font-medium text-rose-600"}>
                {titleCase(profile.hazard_zone)} zone
              </span>
              <span>· {profile.household_dependents} dependent(s)</span>
              <span>· {profile.account_tenure_months}mo tenure</span>
              {!profile.is_borrower && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                  depositor-only
                </span>
              )}
              {profile.rsbsa_registered && (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] font-medium text-emerald-800">
                  RSBSA-registered
                </span>
              )}
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
          screen sees. The FinHealth score is a transparent composite of the five dimensions below.
        </div>
      </Card>

      {/* Five dimension cards with drivers */}
      <div className="grid gap-3 md:grid-cols-2">
        {orderedDims.map(([key, dim]) => (
          <Card key={key} className={dim.insufficient_data ? "opacity-70" : ""}>
            <div className="flex items-center justify-between">
              <div className="font-semibold">
                {DIMENSION_LABELS[key] ?? titleCase(key)}
                {dim.ml_assisted && (
                  <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-indigo-700">
                    ML-assisted
                  </span>
                )}
                {dim.insufficient_data && (
                  <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                    insufficient data
                  </span>
                )}
              </div>
              <div className="text-2xl font-bold tabular-nums text-slate-800">
                {dim.insufficient_data ? "—" : dim.score}
              </div>
            </div>
            {!dim.insufficient_data && (
              <div className="mt-2">
                <ScoreBar score={dim.score} />
              </div>
            )}
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

      {/* Protection gap manifest */}
      <Card>
        <div className="mb-2 font-semibold">
          Protection gap manifest — required protection not held
        </div>
        {profile.resilience_gap.length === 0 ? (
          <div className="text-sm text-emerald-700">
            All exposure-required protection is in place.
          </div>
        ) : (
          <ul className="space-y-2">
            {profile.resilience_gap.map((g) => (
              <li key={g.type} className="flex items-start justify-between gap-2 text-sm">
                <span className="flex items-start gap-2">
                  <SeverityChip level={g.severity_label} />
                  <span>
                    <span className="font-semibold">{titleCase(g.type)}</span>
                    <span className="text-slate-600"> — {g.reason}</span>
                  </span>
                </span>
                <span className="whitespace-nowrap text-xs font-medium text-rose-700">
                  ~{peso(g.estimated_loss)} at risk
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

      {/* Recommendations — three-tier adoption model */}
      <Card>
        <div className="mb-1 font-semibold">Protection recommendations</div>
        {recs ? (
          <>
            <div className="mb-3 text-xs text-slate-500">
              Disposable income: {peso(recs.disposable_income)}/mo · {recs.note}
            </div>
            <div className="space-y-4">
              {tiers.map((tier) => {
                const items = recommended.filter((r) => r.tier === tier);
                if (items.length === 0) return null;
                return (
                  <div key={tier}>
                    <div className="mb-2">
                      <TierBadge tier={tier} />
                    </div>
                    <div className="space-y-2">
                      {items.map((r, i) => (
                        <RecCard key={i} rec={r} tier={tier} />
                      ))}
                    </div>
                  </div>
                );
              })}

              {unaffordable.length > 0 && (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                    Unmet need — no affordable product in any tier
                  </div>
                  <div className="space-y-2">
                    {unaffordable.map((r, i) => (
                      <div key={i} className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                        <div className="flex items-center justify-between">
                          <div className="font-semibold text-amber-900">
                            {titleCase(r.gap_type)} — protection gap, no affordable product
                          </div>
                          <SeverityChip level={r.severity_label} />
                        </div>
                        <p className="mt-1.5 text-sm text-amber-800">{r.rationale}</p>
                      </div>
                    ))}
                  </div>
                </div>
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

function RecCard({ rec, tier }: { rec: Recommendation; tier: Tier }) {
  const p = rec.product!;
  const free = tier === "A" || p.monthly_premium === 0;
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">
          {p.name}{" "}
          <span className="text-xs font-normal text-slate-500">
            {p.provider} · {titleCase(rec.gap_type)} · {peso(p.coverage_amount)} cover
          </span>
        </div>
        <SeverityChip level={rec.severity_label} />
      </div>
      <p className="mt-1.5 text-sm text-slate-600">{rec.rationale}</p>
      <div className="mt-2 flex flex-wrap gap-4 text-xs">
        <span className="font-medium">
          {free ? (
            <span className="text-emerald-700">Free — 100% premium subsidy</span>
          ) : (
            <>
              {peso(p.monthly_premium)}/mo = {rec.premium_pct_of_disposable}% of disposable income
            </>
          )}
        </span>
        <span className="text-slate-500">
          Commission to institution:{" "}
          {free ? "₱0 (government coverage)" : `${peso(rec.projected_annual_commission ?? 0)}/yr`}
        </span>
      </div>
      {rec.enrollment_pathway && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded bg-slate-50 px-2.5 py-1.5">
          <span className="text-xs text-slate-600">{rec.enrollment_pathway}</span>
          <button
            className={`whitespace-nowrap rounded-md px-3 py-1 text-xs font-semibold text-white ${TIER_STYLE[tier].btn}`}
          >
            {TIER_ACTION[tier]}
          </button>
        </div>
      )}
    </div>
  );
}
