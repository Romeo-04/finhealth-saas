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
DIMENSION_WEIGHTS = {
    "income_stability": 0.25,
    "savings_liquidity": 0.25,
    "debt_burden": 0.25,
    "resilience_protection": 0.25,
}

# Band thresholds on the 0-100 overall score.
BAND_HEALTHY_MIN = 70
BAND_COPING_MIN = 40

# Income stability
INCOME_DIVERSITY_BONUS_PER_SOURCE = 5   # per source beyond the first
INCOME_DIVERSITY_BONUS_CAP = 10
# Slope (as fraction of mean income per month) beyond which the negative-trend
# penalty starts; at 2x this slope the full penalty applies.
INCOME_TREND_SLOPE_THRESHOLD = 0.01
INCOME_TREND_PENALTY_MAX = 10

# Whether to apply the clearly-labelled ML-assisted refinement to the income
# stability subscore. The rule-based score always works standalone.
USE_ML_INCOME_REFINEMENT = True
# The refined score is blended: final = (1-w)*rule_based + w*ml_prediction
ML_REFINEMENT_BLEND_WEIGHT = 0.25

# Savings & liquidity benchmark bands (months of essential expenses covered).
# (upper_bound_months, score_at_lower_edge, score_at_upper_edge)
SAVINGS_BANDS = [
    (1.0, 0, 40),
    (3.0, 40, 70),
    (6.0, 70, 90),
]
SAVINGS_TOP_SCORE = 100  # score approached at/beyond 6+ months (90 -> 100)
SAVINGS_BENCHMARK_MONTHS = 3.0  # the "resilient" benchmark quoted in drivers

# Debt burden DSR bands: (dsr_upper_bound, score_at_dsr_lower, score_at_dsr_upper)
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

# Resilience & protection severity weights for the required-protection set.
SEVERITY_HIGH = 3
SEVERITY_MEDIUM = 2

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
