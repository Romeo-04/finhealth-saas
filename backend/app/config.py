"""
Central configuration for the FinHealth scoring engine and recommendation layer.

Everything that a hackathon judge might ask "why this number?" about lives here,
so it can be discussed and tuned live without touching the engine code.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
SYNTHETIC_CLIENT_COUNT = 150

# ---------------------------------------------------------------------------
# Layer 2 — scoring engine
# ---------------------------------------------------------------------------

# Dimension weights for the overall FinHealth score. Must sum to 1.0.
# Revised architecture: five dimensions — Spend, Save, Borrow, Plan, Resilience.
DIMENSION_WEIGHTS = {
    "spend": 0.20,
    "save": 0.20,
    "borrow": 0.20,
    "plan": 0.20,
    "resilience": 0.20,
}

# Band thresholds on the 0-100 overall score.
BAND_HEALTHY_MIN = 70
BAND_COPING_MIN = 40

# --- Spend (expenditure pattern) -------------------------------------------
# Expense-to-income ratio bands: (ratio_upper_bound, score_at_lower, score_at_upper)
# Lower spend ratio => more margin => higher score.
SPEND_RATIO_BANDS = [
    (0.50, 100, 88),
    (0.70, 88, 68),
    (0.85, 68, 45),
    (1.00, 45, 20),
]
SPEND_RATIO_WORST_SCORE = 0  # ratio >= 1.0 (spending at/above income) -> 20 -> 0
# Expense-volatility penalty: erratic spending is a planning risk. CV above the
# threshold starts costing points, up to the max at 2x the threshold.
SPEND_VOLATILITY_CV_THRESHOLD = 0.15
SPEND_VOLATILITY_PENALTY_MAX = 12

# Whether to apply the clearly-labelled ML-assisted refinement to the Spend
# subscore (income/expense pattern). The rule-based score always works alone.
USE_ML_INCOME_REFINEMENT = True
# The refined score is blended: final = (1-w)*rule_based + w*ml_prediction
ML_REFINEMENT_BLEND_WEIGHT = 0.25

# --- Save (savings & liquidity) --------------------------------------------
# Benchmark bands (months of essential expenses covered).
# (upper_bound_months, score_at_lower_edge, score_at_upper_edge)
SAVINGS_BANDS = [
    (1.0, 0, 40),
    (3.0, 40, 70),
    (6.0, 70, 90),
]
SAVINGS_TOP_SCORE = 100  # score approached at/beyond 6+ months (90 -> 100)
SAVINGS_BENCHMARK_MONTHS = 3.0  # the "resilient" benchmark quoted in drivers
# Deposit-consistency factor: a client who saves regularly scales the buffer
# score up; erratic/no deposits scales it down. Maps regularity 0->1 to factor.
DEPOSIT_REGULARITY_FACTOR_MIN = 0.85
DEPOSIT_REGULARITY_FACTOR_MAX = 1.05

# --- Plan (forward-looking financial behaviour) ----------------------------
# Account tenure (months) scored on a saturating curve: 0 -> 0, TENURE_FULL -> 100.
PLAN_TENURE_FULL_MONTHS = 48
# Product diversification: holding across savings / credit / insurance classes.
# score contribution = min(classes, cap) / cap * 100.
PLAN_DIVERSIFICATION_CAP = 3
# Sub-weights within Plan (must sum to 1.0): tenure, diversification, regularity.
PLAN_SUBWEIGHTS = {"tenure": 0.40, "diversification": 0.35, "regularity": 0.25}

# --- Borrow (credit use & serviceability) ----------------------------------
# DSR bands: (dsr_upper_bound, score_at_dsr_lower, score_at_dsr_upper)
DSR_BANDS = [
    (0.20, 100, 85),
    (0.35, 85, 65),
    (0.50, 65, 40),
]
DSR_WORST_SCORE = 0  # score approached as DSR -> 1.0 beyond 0.50 (40 -> 0)
# Repayment factor: linearly maps on_time_ratio 0.0 -> 0.85, 1.0 -> 1.05
REPAYMENT_FACTOR_MIN = 0.85
REPAYMENT_FACTOR_MAX = 1.05
CONCURRENT_LOAN_PENALTY = 8       # subtracted per loan beyond the 2nd
CONCURRENT_LOAN_PENALTY_CAP = 16
# Non-borrower clients (no loans, no CRDPh signal) have no credit to assess.
# The Borrow dimension is flagged insufficient-data and EXCLUDED from the
# composite (weights renormalized over the dimensions that do have data),
# rather than silently scored as if perfect.
BORROW_INSUFFICIENT_DATA_PLACEHOLDER = 50  # shown in UI only; not weighted

# --- Resilience & protection ------------------------------------------------
# Severity weights for the required-protection set.
SEVERITY_HIGH = 3
SEVERITY_MEDIUM = 2
# Estimated-loss magnitude if an uninsured risk materializes, as a multiple of
# MEAN MONTHLY INCOME (plus, for calamity, the client's liquid savings). Feeds
# the protection-gap manifest so the unmet need is quantified, not just named.
ESTIMATED_LOSS_INCOME_MULTIPLE = {
    "crop": 4,        # roughly one lost cropping season of income
    "calamity": 3,    # storm disruption + rebuild (savings added on top)
    "property": 5,    # livelihood asset replacement
    "life": 24,       # ~2 years of income replacement for dependents
    "health": 3,      # major hospitalization episode
    "accident": 3,    # disability income bridge
}

# Proxy credit signal (the deliberately-narrow comparator): weights for the
# two ingredients a traditional credit screen would look at.
PROXY_CREDIT_ON_TIME_WEIGHT = 0.65
PROXY_CREDIT_DSR_WEIGHT = 0.35

# ---------------------------------------------------------------------------
# Layer 3 — recommendation
# ---------------------------------------------------------------------------

# A premium is affordable only if <= this share of monthly disposable income...
AFFORDABILITY_DISPOSABLE_SHARE = 0.10
# ...AND <= this absolute monthly cap, modelling the RA 10607 microinsurance
# idea that premiums must stay small relative to the daily minimum wage
# (NCR daily minimum wage ~PHP 645; we cap at ~1 daily wage per month).
MICROINSURANCE_MONTHLY_PREMIUM_CAP = 650.0

# Commission to the institution, as a share of annual premium. Configurable so
# the incentive conversation is explicit, not buried.
COMMISSION_RATE = 0.20

# ---------------------------------------------------------------------------
# Simulation (longitudinal tracking)
# ---------------------------------------------------------------------------
SHOCK_QUARTER = 3                 # 1-indexed quarter when the typhoon hits
SHOCK_INCOME_DROP_UNPROTECTED = 0.55   # fraction of income lost in shock quarter
SHOCK_INCOME_DROP_PROTECTED = 0.20
SHOCK_SAVINGS_DRAIN_UNPROTECTED = 0.80 # fraction of liquid savings consumed
SHOCK_SAVINGS_DRAIN_PROTECTED = 0.25
RECOVERY_RATE_PROTECTED = 0.90    # share of the drop recovered by next quarter
RECOVERY_RATE_UNPROTECTED = 0.30
