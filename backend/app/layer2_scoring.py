"""
Layer 2 — the financial-health scoring engine.

NOT a credit-scoring model: it does not predict default probability. It builds
a multi-dimensional health profile across four dimensions and surfaces a
resilience gap. The overall score is a transparent weighted composite of
explainable subscores — there is no top-level model. ML appears only inside
the income-stability subscore as a clearly labelled, optional refinement.

Every scoring function returns {score, drivers: [{label, detail, raw_value}]}.
"""
from __future__ import annotations

import statistics

from . import config
from .schema import Client, DimensionScore, Driver, GapItem, HealthProfile


def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def _interpolate(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


# ---------------------------------------------------------------------------
# 4.1 Income stability (rule-based primary, optional labelled ML refinement)
# ---------------------------------------------------------------------------

def score_income_stability(client: Client, ml_model=None) -> DimensionScore:
    income = client.monthly_income
    mean = statistics.mean(income)
    std = statistics.pstdev(income)
    cv = std / mean if mean > 0 else 1.0

    base = _clamp(100 * (1 - cv))

    bonus = min(config.INCOME_DIVERSITY_BONUS_CAP,
                (client.income_sources - 1) * config.INCOME_DIVERSITY_BONUS_PER_SOURCE)

    # Simple least-squares slope over the 12 months, as fraction of mean/month.
    n = len(income)
    xs = range(n)
    x_mean = (n - 1) / 2
    slope = sum((x - x_mean) * (y - mean) for x, y in zip(xs, income)) / \
        sum((x - x_mean) ** 2 for x in xs)
    rel_slope = slope / mean if mean > 0 else 0.0

    penalty = 0.0
    if rel_slope < -config.INCOME_TREND_SLOPE_THRESHOLD:
        # Penalty scales from 0 at the threshold to the max at 2x threshold.
        severity = min(1.0, (-rel_slope - config.INCOME_TREND_SLOPE_THRESHOLD)
                       / config.INCOME_TREND_SLOPE_THRESHOLD)
        penalty = severity * config.INCOME_TREND_PENALTY_MAX

    rule_score = _clamp(base + bonus - penalty)

    trend_word = ("declining" if rel_slope < -config.INCOME_TREND_SLOPE_THRESHOLD
                  else "rising" if rel_slope > config.INCOME_TREND_SLOPE_THRESHOLD
                  else "flat")
    drivers = [
        Driver(label="Income volatility (CV)",
               detail=f"Monthly income varies {cv:.0%} around its mean of "
                      f"₱{mean:,.0f} — {'high' if cv > 0.35 else 'moderate' if cv > 0.15 else 'low'} "
                      f"volatility for planning and repayment.",
               raw_value=round(cv, 3)),
        Driver(label="Income sources",
               detail=f"{client.income_sources} income source(s); diversification adds "
                      f"+{bonus:.0f} points (each extra source cushions a shock to the other).",
               raw_value=client.income_sources),
        Driver(label="12-month trend",
               detail=f"Income trend is {trend_word} "
                      f"({rel_slope * 100:+.1f}% of mean per month)"
                      + (f"; declining trend costs {penalty:.0f} points." if penalty else "."),
               raw_value=round(rel_slope, 4)),
    ]

    ml_assisted = False
    final = rule_score
    if ml_model is not None and config.USE_ML_INCOME_REFINEMENT:
        try:
            features = _income_features(client)
            ml_pred = float(_clamp(ml_model.predict([features])[0]))
            w = config.ML_REFINEMENT_BLEND_WEIGHT
            final = _clamp((1 - w) * rule_score + w * ml_pred)
            ml_assisted = True
            drivers.append(Driver(
                label="ML-assisted refinement",
                detail=f"A GradientBoostingRegressor (trained on synthetic seasonal "
                       f"patterns) suggests {ml_pred:.0f}; blended at {w:.0%} weight "
                       f"with the rule-based score of {rule_score:.0f}. "
                       f"Rule-based score stands alone if the model is absent.",
                raw_value=round(ml_pred, 1)))
        except Exception:
            final = rule_score  # rule-based always works standalone

    return DimensionScore(score=round(final), drivers=drivers, ml_assisted=ml_assisted)


def _income_features(client: Client) -> list[float]:
    """Feature vector for the ML refinement: summary stats of the income series."""
    income = client.monthly_income
    mean = statistics.mean(income)
    std = statistics.pstdev(income)
    return [
        std / mean if mean else 1.0,                 # cv
        min(income) / mean if mean else 0.0,         # worst month vs mean
        max(income) / mean if mean else 0.0,         # best month vs mean
        float(client.income_sources),
        sum(1 for m in income if m < 0.6 * mean),    # count of lean months
    ]


def train_income_ml_model(clients: list[Client]):
    """Train the clearly-labelled, optional ML sub-component.

    Target: a 'stability' signal derived from out-of-band properties of the
    synthetic series (lean-month depth and dispersion). Used ONLY to refine
    the income-stability subscore — never the overall score.
    Returns None if scikit-learn is unavailable; the engine degrades
    gracefully to pure rule-based scoring.
    """
    if not config.USE_ML_INCOME_REFINEMENT:
        return None
    try:
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        return None

    X, y = [], []
    for c in clients:
        income = c.monthly_income
        mean = statistics.mean(income)
        cv = statistics.pstdev(income) / mean if mean else 1.0
        lean_depth = 1.0 - (min(income) / mean if mean else 0.0)
        # Synthetic stability target: volatility + lean-season depth.
        target = _clamp(100 * (1 - 0.8 * cv - 0.25 * lean_depth))
        X.append(_income_features(c))
        y.append(target)
    if len(X) < 20:
        return None
    model = GradientBoostingRegressor(random_state=config.RANDOM_SEED)
    model.fit(X, y)
    return model


# ---------------------------------------------------------------------------
# 4.2 Savings & liquidity adequacy (deterministic, benchmark-aligned)
# ---------------------------------------------------------------------------

def score_savings_liquidity(client: Client) -> DimensionScore:
    expenses = client.monthly_essential_expenses
    months = client.liquid_savings / expenses if expenses > 0 else 0.0

    prev_bound = 0.0
    score = None
    for upper, lo, hi in config.SAVINGS_BANDS:
        if months < upper:
            score = _interpolate(months, prev_bound, upper, lo, hi)
            break
        prev_bound = upper
    if score is None:
        # >= 6 months: interpolate 90 -> 100, saturating at 12 months.
        score = _interpolate(min(months, 12), 6, 12, 90, config.SAVINGS_TOP_SCORE)

    drivers = [
        Driver(label="Months of expenses covered",
               detail=f"Liquid savings of ₱{client.liquid_savings:,.0f} cover "
                      f"{months:.1f} month(s) of essential expenses "
                      f"(₱{expenses:,.0f}/month); benchmark for resilience is "
                      f"{config.SAVINGS_BENCHMARK_MONTHS:.0f}+ months.",
               raw_value=round(months, 2)),
        Driver(label="Buffer assessment",
               detail=("No meaningful emergency buffer — one bad month forces borrowing or asset sale."
                       if months < 1 else
                       "Partial buffer — can absorb a short disruption but not a full season."
                       if months < 3 else
                       "Adequate buffer by the financial-health benchmark."),
               raw_value=f"{months:.1f} months"),
    ]
    return DimensionScore(score=round(_clamp(score)), drivers=drivers)


# ---------------------------------------------------------------------------
# 4.3 Debt burden & serviceability (deterministic)
# ---------------------------------------------------------------------------

def score_debt_burden(client: Client) -> DimensionScore:
    mean_income = statistics.mean(client.monthly_income)
    debt_service = sum(loan["monthly_payment"] for loan in client.loans)
    dsr = debt_service / mean_income if mean_income > 0 else 1.0

    prev_bound = 0.0
    base = None
    for upper, hi, lo in config.DSR_BANDS:  # note: score falls as DSR rises
        if dsr <= upper:
            base = _interpolate(dsr, prev_bound, upper, hi, lo)
            break
        prev_bound = upper
    if base is None:
        # DSR > 0.50: interpolate 40 -> 0, saturating at DSR 1.0.
        base = _interpolate(min(dsr, 1.0), 0.50, 1.0, 40, config.DSR_WORST_SCORE)

    repayment_factor = _interpolate(client.on_time_ratio, 0.0, 1.0,
                                    config.REPAYMENT_FACTOR_MIN,
                                    config.REPAYMENT_FACTOR_MAX)

    n_loans = len(client.loans)
    loan_penalty = min(config.CONCURRENT_LOAN_PENALTY_CAP,
                       max(0, n_loans - 2) * config.CONCURRENT_LOAN_PENALTY)

    score = _clamp(base * repayment_factor - loan_penalty)

    drivers = [
        Driver(label="Debt service ratio",
               detail=f"₱{debt_service:,.0f}/month in loan payments is {dsr:.0%} of mean "
                      f"income — {'comfortable (≤20%)' if dsr <= 0.20 else 'manageable (20–35%)' if dsr <= 0.35 else 'strained (35–50%)' if dsr <= 0.50 else 'over-extended (>50%)'}.",
               raw_value=round(dsr, 3)),
        Driver(label="Repayment history",
               detail=f"{client.on_time_ratio:.0%} of payments on time "
                      f"(score scaled by ×{repayment_factor:.2f}).",
               raw_value=client.on_time_ratio),
        Driver(label="Active loans",
               detail=f"{n_loans} active loan(s)"
                      + (f"; {n_loans}+ concurrent loans costs {loan_penalty:.0f} points "
                         f"(juggling lenders raises rollover risk)." if loan_penalty else "."),
               raw_value=n_loans),
    ]
    return DimensionScore(score=round(score), drivers=drivers)


# ---------------------------------------------------------------------------
# 4.4 Resilience & protection (deterministic, exposure-aware)
# ---------------------------------------------------------------------------

def required_protection(client: Client) -> list[GapItem]:
    """Derive the required-protection set from real-world exposure, with
    severity weights. Returns ALL required types (held or not)."""
    required: list[GapItem] = []
    if client.hazard_zone in ("typhoon", "flood"):
        required.append(GapItem(
            type="calamity", severity=config.SEVERITY_HIGH, severity_label="high",
            reason=f"Lives in a {client.hazard_zone}-exposed municipality "
                   f"({client.municipality})."))
        # Treat asset-holding livelihoods as having insurable property.
        if client.livelihood in ("sari_sari_store", "tricycle_driver",
                                 "market_vendor", "fishing", "rice_farming"):
            required.append(GapItem(
                type="property", severity=config.SEVERITY_MEDIUM, severity_label="medium",
                reason="Livelihood assets (stock, equipment, boat/vehicle) sit in a "
                       "hazard-exposed area."))
    if client.livelihood in ("rice_farming", "fishing"):
        required.append(GapItem(
            type="crop", severity=config.SEVERITY_HIGH, severity_label="high",
            reason=f"Income from {client.livelihood.replace('_', ' ')} is exposed to "
                   f"weather shocks — one bad season interrupts all inflows."))
    if client.household_dependents > 0:
        required.append(GapItem(
            type="life", severity=config.SEVERITY_MEDIUM, severity_label="medium",
            reason=f"{client.household_dependents} dependent(s) rely on this income."))
    required.append(GapItem(
        type="health", severity=config.SEVERITY_MEDIUM, severity_label="medium",
        reason="A health emergency is the most common unplanned expense for any household."))
    return required


def score_resilience_protection(client: Client) -> tuple[DimensionScore, list[GapItem]]:
    required = required_protection(client)
    held = set(client.insurance_held)

    total_weight = sum(item.severity for item in required)
    held_weight = sum(item.severity for item in required if item.type in held)
    coverage = held_weight / total_weight if total_weight else 1.0
    score = round(100 * coverage)

    gap = sorted([item for item in required if item.type not in held],
                 key=lambda g: -g.severity)

    missing_high = [g.type for g in gap if g.severity_label == "high"]
    drivers = [
        Driver(label="Exposure-weighted coverage",
               detail=f"Holds {held_weight} of {total_weight} severity-weighted "
                      f"protection units required by actual exposure "
                      f"({coverage:.0%} covered).",
               raw_value=round(coverage, 2)),
        Driver(label="Protection held",
               detail=("Holds: " + ", ".join(sorted(held))) if held
                      else "Holds no insurance of any kind.",
               raw_value=", ".join(sorted(held)) or "none"),
    ]
    if missing_high:
        drivers.append(Driver(
            label="Missing high-severity protection",
            detail=f"Missing {' and '.join(missing_high)} cover despite direct exposure — "
                   f"this is the resilience gap that would turn a shock into a default.",
            raw_value=", ".join(missing_high)))
    if client.prior_shock_last_24m:
        drivers.append(Driver(
            label="Prior shock",
            detail="Experienced a shock in the last 24 months — exposure is "
                   "demonstrated, not hypothetical.",
            raw_value="yes"))

    return DimensionScore(score=score, drivers=drivers), gap


# ---------------------------------------------------------------------------
# 4.5 Overall composite + proxy credit signal
# ---------------------------------------------------------------------------

def band_for(score: float) -> str:
    if score >= config.BAND_HEALTHY_MIN:
        return "Healthy"
    if score >= config.BAND_COPING_MIN:
        return "Coping"
    return "Vulnerable"


def proxy_credit_signal(client: Client) -> int:
    """A deliberately narrow traditional-credit-style proxy built ONLY from
    repayment history and DSR. Shown beside the FinHealth score to dramatize
    that 'repays fine today' is not the same as 'financially healthy'."""
    mean_income = statistics.mean(client.monthly_income)
    debt_service = sum(loan["monthly_payment"] for loan in client.loans)
    dsr = debt_service / mean_income if mean_income > 0 else 1.0
    dsr_component = _clamp(100 * (1 - dsr / 0.6))
    on_time_component = 100 * client.on_time_ratio
    return round(config.PROXY_CREDIT_ON_TIME_WEIGHT * on_time_component
                 + config.PROXY_CREDIT_DSR_WEIGHT * dsr_component)


def build_profile(client: Client, ml_model=None) -> HealthProfile:
    income_dim = score_income_stability(client, ml_model)
    savings_dim = score_savings_liquidity(client)
    debt_dim = score_debt_burden(client)
    resilience_dim, gap = score_resilience_protection(client)

    dims = {
        "income_stability": income_dim,
        "savings_liquidity": savings_dim,
        "debt_burden": debt_dim,
        "resilience_protection": resilience_dim,
    }
    overall = round(sum(config.DIMENSION_WEIGHTS[k] * d.score for k, d in dims.items()))
    proxy = proxy_credit_signal(client)

    return HealthProfile(
        client_id=client.client_id,
        name=client.name,
        municipality=client.municipality,
        hazard_zone=client.hazard_zone,
        livelihood=client.livelihood,
        household_dependents=client.household_dependents,
        overall_score=overall,
        band=band_for(overall),
        dimensions=dims,
        resilience_gap=gap,
        proxy_credit_signal=proxy,
        proxy_credit_band=band_for(proxy),
        imputed_fields=client.imputed_fields,
        mean_monthly_income=round(statistics.mean(client.monthly_income), 2),
        monthly_essential_expenses=client.monthly_essential_expenses,
        liquid_savings=client.liquid_savings,
        monthly_debt_service=round(sum(l["monthly_payment"] for l in client.loans), 2),
        insurance_held=client.insurance_held,
        monthly_income=client.monthly_income,
    )
