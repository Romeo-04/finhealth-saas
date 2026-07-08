// Typed client for the FastAPI backend. Shapes mirror backend/app/schema.py.
const BASE = "http://localhost:8000";

export interface Driver {
  label: string;
  detail: string;
  raw_value: number | string;
}

export interface DimensionScore {
  score: number;
  drivers: Driver[];
  ml_assisted: boolean;
}

export interface GapItem {
  type: string;
  severity: number;
  severity_label: "high" | "medium";
  reason: string;
}

export interface HealthProfile {
  client_id: string;
  name: string;
  municipality: string;
  hazard_zone: string;
  livelihood: string;
  household_dependents: number;
  overall_score: number;
  band: Band;
  dimensions: Record<string, DimensionScore>;
  resilience_gap: GapItem[];
  proxy_credit_signal: number;
  proxy_credit_band: Band;
  imputed_fields: string[];
  mean_monthly_income: number;
  monthly_essential_expenses: number;
  liquid_savings: number;
  monthly_debt_service: number;
  insurance_held: string[];
  monthly_income: number[];
}

export type Band = "Healthy" | "Coping" | "Vulnerable";

export interface ClientSummary {
  client_id: string;
  name: string;
  municipality: string;
  hazard_zone: string;
  livelihood: string;
  overall_score: number;
  band: Band;
  has_resilience_gap: boolean;
  proxy_credit_signal: number;
}

export interface Product {
  id: string;
  type: string;
  provider: string;
  name: string;
  coverage_amount: number;
  monthly_premium: number;
  description: string;
}

export interface Recommendation {
  status: "recommended" | "protection_gap_unaffordable";
  gap_type: string;
  severity_label: "high" | "medium";
  product: Product | null;
  rationale: string;
  premium_pct_of_disposable: number | null;
  projected_annual_commission: number | null;
}

export interface RecommendationResponse {
  client_id: string;
  disposable_income: number;
  recommendations: Recommendation[];
  note: string;
}

export interface PortfolioStats {
  total_clients: number;
  band_counts: Record<Band, number>;
  band_pct: Record<Band, number>;
  pct_with_resilience_gap: number;
  aggregate_uninsured_exposure: number;
  projected_annual_commission: number;
}

export interface QuarterPoint {
  quarter: string;
  shock: boolean;
  mean_score: number;
  band_distribution: Record<Band, number>;
}

export interface SimulationResult {
  shock_quarter: string;
  shock_description: string;
  affected_clients: number;
  cohorts: {
    protected: { size: number; trajectory: QuarterPoint[] };
    unprotected: { size: number; trajectory: QuarterPoint[] };
  };
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  clients: () => get<ClientSummary[]>("/clients"),
  client: (id: string) => get<HealthProfile>(`/clients/${id}`),
  recommendations: (id: string) =>
    get<RecommendationResponse>(`/clients/${id}/recommendations`),
  portfolio: () => get<PortfolioStats>("/portfolio"),
  simulate: async (): Promise<SimulationResult> => {
    const res = await fetch(`${BASE}/simulate`, { method: "POST" });
    if (!res.ok) throw new Error(`/simulate: ${res.status}`);
    return res.json();
  },
};

export const peso = (n: number) =>
  "₱" + n.toLocaleString("en-PH", { maximumFractionDigits: 0 });
