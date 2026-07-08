"""
Layer 2 — the financial-health scoring engine.

NOT a credit-scoring model: it does not predict default probability. It builds
a multi-dimensional health profile across the five dimensions of the revised
architecture — Spend, Save, Borrow, Plan, Resilience — and surfaces a
quantified protection-gap manifest. The overall score is a transparent
weighted composite of explainable subscores; there is no top-level model. ML
appears only inside the Spend subscore as a clearly labelled, optional
refinement. A dimension with no data to assess (e.g. Borrow for a non-borrower)
is flagged insufficient-data and excluded from the composite rather than being
silently scored as if perfect.

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


def _banded(value: float, bands: list[tuple[float, float, float]],
            end_score: float, end_bound: float) -> float:
    """Piecewise-linear lookup. `bands` = [(upper, score_at_band_lower_edge,
    score_at_band_upper_edge), ...] assumed contiguous from 0. Values beyond the
    last band interpolate from the last band's upper score toward `end_score`
    reached at `end_bound`."""
    prev = 0.0
    for upper, lo, hi in bands:
        if value <= upper:
            return _interpolate(value, prev, upper, lo, hi)
        prev = upper
    last_upper, _, last_hi = bands[-1]
    return _interpolate(min(value, end_bound), last_upper, end_bound,
                        last_hi, end_score)


# ---------------------------------------------------------------------------
# Spend — expenditure pattern (rule-based primary, optional labelled ML refinement)
# ---------------------------------------------------------------------------

def score_spend(client: Client, ml_model=None) -> DimensionScore:
    income = client.monthly_income
    expenses = client.monthly_expenses
    mean_income = statistics.mean(income)
    mean_expense = statistics.mean(expenses)
    ratio = mean_expense / mean_income if mean_income > 0 else 1.5

    base = _banded(ratio, config.SPEND_RATIO_BANDS,
                   config.SPEND_RATIO_WORST_SCORE, end_bound=1.5)

    exp_cv = statistics.pstdev(expenses) / mean_expense if mean_expense > 0 else 0.0
    penalty = 0.0
    if exp_cv > config.SPEND_VOLATILITY_CV_THRESHOLD:
        severity = min(1.0, (exp_cv - config.SPEND_VOLATILITY_CV_THRESHOLD)
                       / config.SPEND_VOLATILITY_CV_THRESHOLD)
        penalty = severity * config.SPEND_VOLATILITY_PENALTY_MAX

    rule_score = _clamp(base - penalty)

    drivers = [
        Driver(label="Expense-to-income ratio",
               detail=f"Spends ₱{mean_expense:,.0f} against ₱{mean_income:,.0f} mean "
                      f"income — {ratio:.0%} of income goes to essentials "
                      f"({'thin' if ratio > 0.85 else 'tight' if ratio > 0.7 else 'comfortable'} margin).",
               raw_value=round(ratio, 3)),
        Driver(label="Expense volatility",
               detail=f"Month-to-month essential spending varies {exp_cv:.0%} around its mean"
                      + (f"; erratic spending costs {penalty:.0f} points." if penalty
                         else " — steady and predictable."),
               raw_value=round(exp_cv, 3)),
    ]

    ml_assisted = False
    final = rule_score
    if ml_model is not None and config.USE_ML_INCOME_REFINEMENT:
        try:
            features = _spend_features(client)
            ml_pred = float(_clamp(ml_model.predict([features])[0]))
            w = config.ML_REFINEMENT_BLEND_WEIGHT
            final = _clamp((1 - w) * rule_score + w * ml_pred)
            ml_assisted = True
            drivers.append(Driver(
                label="ML-assisted refinement",
                detail=f"A GradientBoostingRegressor (trained on synthetic seasonal "
                       f"income/expense patterns) suggests {ml_pred:.0f}; blended at "
                       f"{w:.0%} weight with the rule-based score of {rule_score:.0f}. "
                       f"Rule-based score stands alone if the model is absent.",
                raw_value=round(ml_pred, 1)))
        except Exception:
            final = rule_score  # rule-based always works standalone

    return DimensionScore(score=round(final), drivers=drivers, ml_assisted=ml_assisted)


def _spend_features(client: Client) -> list[float]:
    """Feature vector for the ML refinement: income/expense summary stats."""
    income = client.monthly_income
    expenses = client.monthly_expenses
    mean_i = statistics.mean(income)
    mean_e = statistics.mean(expenses)
    return [
        statistics.pstdev(income) / mean_i if mean_i else 1.0,   # income cv
        statistics.pstdev(expenses) / mean_e if mean_e else 0.0,  # expense cv
        mean_e / mean_i if mean_i else 1.5,                       # spend ratio
        min(income) / mean_i if mean_i else 0.0,                  # worst month vs mean
        sum(1 for m in income if m < 0.6 * mean_i),               # lean months
    ]


def train_income_ml_model(clients: list[Client]):
    """Train the clearly-labelled, optional ML sub-component used ONLY to refine
    the Spend subscore. Returns None if scikit-learn is unavailable; the engine
    degrades gracefully to pure rule-based scoring."""
    if not config.USE_ML_INCOME_REFINEMENT:
        return None
    try:
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        return None

    X, y = [], []
    for c in clients:
        income = c.monthly_income
        expenses = c.monthly_expenses
        mean_i = statistics.mean(income)
        mean_e = statistics.mean(expenses)
        cv = statistics.pstdev(income) / mean_i if mean_i else 1.0
        ratio = mean_e / mean_i if mean_i else 1.5
        lean_depth = 1.0 - (min(income) / mean_i if mean_i else 0.0)
        # Synthetic target: low spend ratio + low volatility + shallow lean season.
        target = _clamp(100 * (1 - 0.5 * ratio - 0.3 * cv - 0.2 * lean_depth) + 30)
        X.append(_spend_features(c))
        y.append(target)
    if len(X) < 20:
        return None
    model = GradientBoostingRegressor(random_state=config.RANDOM_SEED)
    model.fit(X, y)
    return model


# ---------------------------------------------------------------------------
# Save — savings & liquidity adequacy (deterministic, benchmark-aligned)
# ---------------------------------------------------------------------------

def score_save(client: Client) -> DimensionScore:
    expenses = client.monthly_essential_expenses
    mean_income = statistics.mean(client.monthly_income)
    months = client.liquid_savings / expenses if expenses > 0 else 0.0
    savings_to_income = client.liquid_savings / mean_income if mean_income > 0 else 0.0

    base = _banded(months, config.SAVINGS_BANDS,
                   config.SAVINGS_TOP_SCORE, end_bound=12)

    # Deposit-consistency scales the buffer score: regular savers are more
    # resilient than a one-off balance suggests, and vice-versa.
    reg = client.savings_deposit_regularity
    reg_factor = _interpolate(reg, 0.0, 1.0,
                              config.DEPOSIT_REGULARITY_FACTOR_MIN,
                              config.DEPOSIT_REGULARITY_FACTOR_MAX)
    score = _clamp(base * reg_factor)

    drivers = [
        Driver(label="Months of expenses covered",
               detail=f"Liquid savings of ₱{client.liquid_savings:,.0f} cover "
                      f"{months:.1f} month(s) of essentials; benchmark for resilience "
                      f"is {config.SAVINGS_BENCHMARK_MONTHS:.0f}+ months.",
               raw_value=round(months, 2)),
        Driver(label="Savings-to-income ratio",
               detail=f"Savings equal {savings_to_income:.1f}× mean monthly income.",
               raw_value=round(savings_to_income, 2)),
        Driver(label="Deposit consistency",
               detail=f"Saves {'regularly' if reg >= 0.6 else 'irregularly' if reg >= 0.3 else 'rarely'} "
                      f"(regularity {reg:.0%}); score scaled ×{reg_factor:.2f}.",
               raw_value=round(reg, 2)),
    ]
    return DimensionScore(score=round(score), drivers=drivers)


# ---------------------------------------------------------------------------
# Borrow — credit use & serviceability (deterministic; insufficient-data aware)
# ---------------------------------------------------------------------------

def score_borrow(client: Client) -> DimensionScore:
    if not client.loans:
        # Non-borrower (depositor / savings-group member). No CRDPh signal in
        # this demo, so there is no credit behaviour to assess.
        return DimensionScore(
            score=config.BORROW_INSUFFICIENT_DATA_PLACEHOLDER,
            insufficient_data=True,
            drivers=[Driver(
                label="No active credit",
                detail="Client holds no active loan and has no CRDPh record in this "
                       "demo — the Borrow dimension is insufficient-data and is "
                       "excluded from the composite (weights renormalized over the "
                       "assessable dimensions).",
                raw_value="insufficient_data")],
        )

    mean_income = statistics.mean(client.monthly_income)
    debt_service = sum(loan["monthly_payment"] for loan in client.loans)
    dsr = debt_service / mean_income if mean_income > 0 else 1.0

    base = _banded(dsr, config.DSR_BANDS, config.DSR_WORST_SCORE, end_bound=1.0)

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
# Plan — forward-looking financial behaviour (deterministic)
# ---------------------------------------------------------------------------

def score_plan(client: Client) -> DimensionScore:
    tenure = client.account_tenure_months
    tenure_score = _clamp(100 * tenure / config.PLAN_TENURE_FULL_MONTHS)

    classes = sum([
        client.liquid_savings > 0,          # savings product
        bool(client.loans),                 # credit product
        bool(client.insurance_held),        # insurance product
    ])
    cap = config.PLAN_DIVERSIFICATION_CAP
    div_score = 100 * min(classes, cap) / cap

    reg_score = 100 * client.savings_deposit_regularity

    sw = config.PLAN_SUBWEIGHTS
    score = _clamp(sw["tenure"] * tenure_score
                   + sw["diversification"] * div_score
                   + sw["regularity"] * reg_score)

    drivers = [
        Driver(label="Account tenure",
               detail=f"{tenure} month(s) with the institution "
                      f"({'well-established' if tenure >= 36 else 'building history' if tenure >= 12 else 'new relationship'}).",
               raw_value=tenure),
        Driver(label="Product diversification",
               detail=f"Holds {classes} of 3 product classes (savings / credit / insurance) — "
                      f"diversified use signals engaged financial planning.",
               raw_value=classes),
        Driver(label="Contribution regularity",
               detail=f"Deposit regularity {client.savings_deposit_regularity:.0%} — "
                      f"{'consistent' if client.savings_deposit_regularity >= 0.6 else 'sporadic'} forward provisioning.",
               raw_value=round(client.savings_deposit_regularity, 2)),
    ]
    return DimensionScore(score=round(score), drivers=drivers)


# ---------------------------------------------------------------------------
# Resilience & protection (deterministic, exposure-aware) + gap manifest
# ---------------------------------------------------------------------------

def _estimated_loss(gap_type: str, mean_income: float, client: Client) -> float:
    mult = config.ESTIMATED_LOSS_INCOME_MULTIPLE.get(gap_type, 3)
    loss = mult * mean_income
    if gap_type == "calamity":
        loss += client.liquid_savings  # a storm also drains the buffer
    return round(loss, 2)


def required_protection(client: Client) -> list[GapItem]:
    """Derive the required-protection set from real-world exposure, with
    severity weights and an estimated loss magnitude per exposure. Returns ALL
    required types (held or not)."""
    mean_income = statistics.mean(client.monthly_income)

    def item(type_, severity, label, reason):
        return GapItem(type=type_, severity=severity, severity_label=label,
                       reason=reason,
                       estimated_loss=_estimated_loss(type_, mean_income, client))

    required: list[GapItem] = []
    if client.hazard_zone in ("typhoon", "flood"):
        required.append(item(
            "calamity", config.SEVERITY_HIGH, "high",
            f"Lives in a {client.hazard_zone}-exposed municipality "
            f"({client.municipality})."))
        if client.livelihood in ("sari_sari_store", "tricycle_driver",
                                 "market_vendor", "fishing", "rice_farming"):
            required.append(item(
                "property", config.SEVERITY_MEDIUM, "medium",
                "Livelihood assets (stock, equipment, boat/vehicle) sit in a "
                "hazard-exposed area."))
    if client.livelihood in ("rice_farming", "fishing"):
        required.append(item(
            "crop", config.SEVERITY_HIGH, "high",
            f"Income from {client.livelihood.replace('_', ' ')} is exposed to "
            f"weather shocks — one bad season interrupts all inflows."))
    if client.household_dependents > 0:
        required.append(item(
            "life", config.SEVERITY_MEDIUM, "medium",
            f"{client.household_dependents} dependent(s) rely on this income."))
    required.append(item(
        "health", config.SEVERITY_MEDIUM, "medium",
        "A health emergency is the most common unplanned expense for any household."))
    return required


def score_resilience(client: Client) -> tuple[DimensionScore, list[GapItem]]:
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
# Overall composite + proxy credit signal
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
    resilience_dim, gap = score_resilience(client)
    dims = {
        "spend": score_spend(client, ml_model),
        "save": score_save(client),
        "borrow": score_borrow(client),
        "plan": score_plan(client),
        "resilience": resilience_dim,
    }

    # Composite over assessable dimensions only — a dimension flagged
    # insufficient-data is excluded and its weight is renormalized away.
    active = {k: d for k, d in dims.items() if not d.insufficient_data}
    total_w = sum(config.DIMENSION_WEIGHTS[k] for k in active)
    overall = round(sum(config.DIMENSION_WEIGHTS[k] * d.score
                        for k, d in active.items()) / total_w) if total_w else 0
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
        account_tenure_months=client.account_tenure_months,
        rsbsa_registered=client.rsbsa_registered,
        is_borrower=bool(client.loans),
    )
