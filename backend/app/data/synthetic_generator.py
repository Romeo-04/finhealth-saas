"""
Synthetic FSP client data generator.

Generates ~150 clients with realistic, correlated distributions:
- livelihood drives income level and volatility (farmers/fishers are seasonal
  and high-variance with a lean season; salaried is low-variance),
- hazard zone correlates with municipality (farming/fishing towns sit in
  typhoon/flood zones),
- savings are thin for most households,
- insurance held is sparse and frequently mismatched to actual exposure,
  so a majority of clients carry a real resilience gap (the point of the demo).

All names and places are synthetic. The RNG is seeded for reproducibility.
A handful of clients are deliberately engineered to demonstrate the
credit-vs-health divergence (good repayment + low DSR, but no buffer and no
protection).
"""
from __future__ import annotations

import json
import random

from .. import config

FIRST_NAMES = [
    "Maria", "Jose", "Juan", "Ana", "Pedro", "Rosa", "Carlos", "Liza",
    "Ramon", "Teresa", "Andres", "Carmen", "Felipe", "Gloria", "Marco",
    "Nena", "Paolo", "Sofia", "Tomas", "Vilma", "Benigno", "Divina",
    "Eduardo", "Fe", "Gregorio", "Imelda", "Lando", "Mirasol", "Nestor", "Perla",
]
LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza",
    "Torres", "Flores", "Ramos", "Villanueva", "Aquino", "Navarro", "Salazar",
    "Domingo", "Castillo", "Marquez", "Padilla", "Soriano", "Velasco",
]

# Synthetic municipalities, each with a dominant hazard profile.
MUNICIPALITIES = {
    "San Isidro":     {"hazard_weights": {"typhoon": 0.70, "flood": 0.20, "low_risk": 0.10}},
    "Bagong Silang":  {"hazard_weights": {"typhoon": 0.15, "flood": 0.70, "low_risk": 0.15}},
    "Malinaw Bay":    {"hazard_weights": {"typhoon": 0.60, "flood": 0.30, "low_risk": 0.10}},
    "Pook Centro":    {"hazard_weights": {"typhoon": 0.10, "flood": 0.15, "low_risk": 0.75}},
    "Tahimik Hills":  {"hazard_weights": {"typhoon": 0.20, "flood": 0.10, "low_risk": 0.70}},
}

# Livelihood profile: (base monthly income range, coefficient of variation
# range, seasonal lean months, typical municipality pool)
LIVELIHOOD_PROFILES = {
    "rice_farming": {
        "income_range": (8000, 16000), "cv_range": (0.40, 0.70),
        "lean_months": [6, 7, 8],  # pre-harvest lean season
        "municipalities": ["San Isidro", "Bagong Silang", "Tahimik Hills"],
    },
    "fishing": {
        "income_range": (7000, 14000), "cv_range": (0.40, 0.70),
        "lean_months": [7, 8, 9],  # habagat storm season
        "municipalities": ["Malinaw Bay", "Bagong Silang"],
    },
    "sari_sari_store": {
        "income_range": (9000, 18000), "cv_range": (0.15, 0.30),
        "lean_months": [],
        "municipalities": list(MUNICIPALITIES),
    },
    "tricycle_driver": {
        "income_range": (8000, 15000), "cv_range": (0.15, 0.30),
        "lean_months": [],
        "municipalities": list(MUNICIPALITIES),
    },
    "market_vendor": {
        "income_range": (8000, 16000), "cv_range": (0.15, 0.30),
        "lean_months": [],
        "municipalities": list(MUNICIPALITIES),
    },
    "salaried": {
        "income_range": (12000, 25000), "cv_range": (0.02, 0.08),
        "lean_months": [],
        "municipalities": ["Pook Centro", "Tahimik Hills"],
    },
}

LIVELIHOOD_MIX = [
    ("rice_farming", 0.28),
    ("fishing", 0.16),
    ("sari_sari_store", 0.16),
    ("tricycle_driver", 0.13),
    ("market_vendor", 0.13),
    ("salaried", 0.14),
]


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _income_series(rng: random.Random, profile: dict, declining: bool) -> list[float]:
    base = rng.uniform(*profile["income_range"])
    cv = rng.uniform(*profile["cv_range"])
    series = []
    for month in range(1, 13):
        value = rng.gauss(base, base * cv)
        if month in profile["lean_months"]:
            value *= rng.uniform(0.35, 0.60)  # lean season collapse
        if declining:
            value *= 1.0 - 0.025 * month  # gentle structural decline
        series.append(round(max(value, base * 0.10), 2))
    return series


def _insurance_held(rng: random.Random, livelihood: str, hazard: str) -> list[str]:
    """Sparse, frequently mismatched coverage — engineered so most clients
    have a real gap. Held cover skews toward life/accident (what gets bundled
    with loans), rarely the crop/calamity cover that exposure actually demands."""
    held: set[str] = set()
    roll = rng.random()
    if roll < 0.30:
        pass  # ~30% hold nothing at all
    elif roll < 0.70:
        held.add(rng.choices(["life", "accident", "health"], weights=[5, 3, 2])[0])
    else:
        held.add("life")
        held.add(rng.choice(["health", "accident"]))
        # Only a minority hold the cover matched to their exposure — enough
        # to form a visible "protected" cohort in the simulation, while the
        # large majority still carry a real gap.
        if rng.random() < 0.45:
            if livelihood in ("rice_farming", "fishing"):
                held.add("crop")
            if hazard in ("typhoon", "flood"):
                held.add("calamity")
    # Independent small chance any exposed client holds matched cover (e.g.
    # enrolled via a coop or LGU programme) — keeps the simulation's
    # "protected" cohort large enough to chart.
    if hazard in ("typhoon", "flood") and rng.random() < 0.12:
        held.add("calamity")
    if livelihood in ("rice_farming", "fishing") and rng.random() < 0.10:
        held.add("crop")
    return sorted(held)


def generate_clients(n: int = config.SYNTHETIC_CLIENT_COUNT,
                     seed: int = config.RANDOM_SEED) -> list[dict]:
    rng = random.Random(seed)
    clients = []
    livelihoods = [lv for lv, _ in LIVELIHOOD_MIX]
    weights = [w for _, w in LIVELIHOOD_MIX]

    for i in range(n):
        livelihood = rng.choices(livelihoods, weights=weights)[0]
        profile = LIVELIHOOD_PROFILES[livelihood]
        municipality = rng.choice(profile["municipalities"])
        hazard_zone = _weighted_choice(rng, MUNICIPALITIES[municipality]["hazard_weights"])

        # Reserve the first few salaried-ish records as deliberate
        # credit-vs-health divergence cases (built below).
        declining = rng.random() < 0.12
        income = _income_series(rng, profile, declining)
        mean_income = sum(income) / len(income)

        # Expenses: 55-85% of mean income for thin-margin households.
        expenses = round(mean_income * rng.uniform(0.55, 0.85), 2)

        # Savings: most are thin (<1 month of expenses), a minority comfortable.
        savings_roll = rng.random()
        if savings_roll < 0.55:
            savings = expenses * rng.uniform(0.05, 0.9)
        elif savings_roll < 0.85:
            savings = expenses * rng.uniform(1.0, 3.0)
        else:
            savings = expenses * rng.uniform(3.0, 8.0)

        # Loans: 0-3 active loans, payments sized to plausible DSRs.
        n_loans = rng.choices([0, 1, 2, 3], weights=[15, 50, 25, 10])[0]
        loans = []
        for _ in range(n_loans):
            principal = round(rng.uniform(5000, 60000), -2)
            months = rng.randint(3, 24)
            # flat-rate style payment with a microfinance-ish add-on
            payment = round(principal / months * rng.uniform(1.05, 1.25), 2)
            loans.append({
                "principal": principal,
                "monthly_payment": payment,
                "months_remaining": months,
            })
        on_time = round(min(1.0, max(0.3, rng.gauss(0.88, 0.12))), 2)

        client = {
            "client_id": f"C{i + 1:04d}",
            "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "municipality": municipality,
            "hazard_zone": hazard_zone,
            "livelihood": livelihood,
            "household_dependents": rng.choices([0, 1, 2, 3, 4, 5], weights=[10, 18, 25, 22, 15, 10])[0],
            "monthly_income": income,
            "income_sources": rng.choices([1, 2, 3], weights=[55, 35, 10])[0],
            "monthly_essential_expenses": expenses,
            "liquid_savings": round(savings, 2),
            "loans": loans,
            "on_time_ratio": on_time,
            "insurance_held": _insurance_held(rng, livelihood, hazard_zone),
            "prior_shock_last_24m": rng.random() < (0.45 if hazard_zone != "low_risk" else 0.12),
            "imputed_fields": [],
        }
        clients.append(client)

    # ----- engineered divergence cases ------------------------------------
    # Perfect repayment + low DSR (looks fine on a credit proxy) but seasonal
    # income, near-zero savings, full exposure, zero protection -> Vulnerable.
    for idx in (10, 47, 92):
        c = clients[idx]
        c["livelihood"] = "rice_farming"
        c["municipality"] = "San Isidro"
        c["hazard_zone"] = "typhoon"
        c["monthly_income"] = _income_series(rng, LIVELIHOOD_PROFILES["rice_farming"], False)
        mean_income = sum(c["monthly_income"]) / 12
        c["monthly_essential_expenses"] = round(mean_income * 0.80, 2)
        c["liquid_savings"] = round(c["monthly_essential_expenses"] * 0.25, 2)
        c["loans"] = [{
            "principal": 20000,
            "monthly_payment": round(mean_income * 0.12, 2),  # DSR ~0.12
            "months_remaining": 12,
        }]
        c["on_time_ratio"] = 1.0
        c["insurance_held"] = []
        c["income_sources"] = 1
        c["household_dependents"] = max(2, c["household_dependents"])

    return clients


def clients_to_csv_rows(clients: list[dict]) -> list[dict]:
    """Flatten clients to CSV-friendly rows (lists JSON-encoded), matching the
    format `POST /ingest` accepts."""
    rows = []
    for c in clients:
        row = dict(c)
        row["monthly_income"] = json.dumps(c["monthly_income"])
        row["loans"] = json.dumps(c["loans"])
        row["insurance_held"] = json.dumps(c["insurance_held"])
        row.pop("imputed_fields", None)
        rows.append(row)
    return rows
