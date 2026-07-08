"""
Layer 3 — risk-informed insurance recommendation.

Takes the ordered resilience gap from Layer 2 and matches each missing
protection type to the best-fit AFFORDABLE product. Two guardrails:

1. Affordability: premium <= 10% of monthly disposable income AND within the
   microinsurance cap (modelling the RA 10607 idea that premiums stay small
   relative to the daily minimum wage).
2. Anti-mis-selling: if a genuine gap exists but no product passes the
   affordability check, return `protection_gap_unaffordable` — surface the
   unmet need, never push a product the client cannot sustain.

The institution's commission is computed and shown explicitly so the revenue
incentive for serving these clients is legible, not hidden.
"""
from __future__ import annotations

import json
import statistics
from functools import lru_cache
from pathlib import Path

from . import config
from .schema import Client, GapItem, Recommendation, RecommendationResponse

PRODUCTS_PATH = Path(__file__).parent / "data" / "products.json"

LIVELIHOOD_LABEL = {
    "rice_farming": "Rice farmer",
    "fishing": "Fishing household",
    "sari_sari_store": "Sari-sari store owner",
    "tricycle_driver": "Tricycle driver",
    "market_vendor": "Market vendor",
    "salaried": "Salaried worker",
}


@lru_cache(maxsize=1)
def load_products() -> list[dict]:
    return json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))


def disposable_income(client: Client) -> float:
    mean_income = statistics.mean(client.monthly_income)
    debt_service = sum(loan["monthly_payment"] for loan in client.loans)
    return mean_income - client.monthly_essential_expenses - debt_service


def _is_affordable(premium: float, disposable: float) -> bool:
    return (premium <= config.AFFORDABILITY_DISPOSABLE_SHARE * max(disposable, 0)
            and premium <= config.MICROINSURANCE_MONTHLY_PREMIUM_CAP)


def _best_fit_product(gap_type: str, client: Client, disposable: float) -> dict | None:
    """Among affordable products of the right type, prefer the most coverage
    per peso; among crop products, prefer the livelihood-matched one."""
    candidates = [p for p in load_products() if p["type"] == gap_type
                  and _is_affordable(p["monthly_premium"], disposable)]
    if not candidates:
        return None
    if gap_type == "crop":
        # Fisher cover for fishing households, rice cover for farmers.
        keyword = "Fisher" if client.livelihood == "fishing" else "Rice"
        matched = [p for p in candidates if keyword.lower() in p["name"].lower()]
        if matched:
            candidates = matched
    return max(candidates, key=lambda p: p["coverage_amount"] / p["monthly_premium"])


def _rationale(gap: GapItem, client: Client, product: dict | None) -> str:
    who = LIVELIHOOD_LABEL.get(client.livelihood, "Client")
    exposure = gap.reason.rstrip(".")
    if gap.type in ("crop", "calamity"):
        consequence = ("one bad season would erase repayment capacity"
                       if gap.type == "crop"
                       else "a single storm would wipe out savings and stall repayments")
    elif gap.type == "life":
        consequence = "the household would lose its main income with no fallback"
    elif gap.type == "health":
        consequence = "a hospitalization would force high-cost borrowing"
    else:
        consequence = "asset loss would interrupt the livelihood itself"
    exposure_clause = exposure[0].lower() + exposure[1:] if exposure else exposure
    base = f"{who} in {client.municipality}: {exposure_clause}, with no {gap.type} cover — {consequence}."
    if product:
        return (f"{base} {product['name']} closes this gap with "
                f"₱{product['coverage_amount']:,.0f} of cover for "
                f"₱{product['monthly_premium']:,.0f}/month.")
    return base


def recommend(client: Client, gap: list[GapItem]) -> RecommendationResponse:
    disposable = disposable_income(client)
    recs: list[Recommendation] = []

    for item in gap:  # already ordered highest severity first by Layer 2
        product = _best_fit_product(item.type, client, disposable)
        if product is None:
            # Genuine gap, no sustainable product -> flag, don't push.
            recs.append(Recommendation(
                status="protection_gap_unaffordable",
                gap_type=item.type,
                severity_label=item.severity_label,
                product=None,
                rationale=_rationale(item, client, None) +
                " No catalogue product fits within 10% of this client's disposable "
                "income — flagged as an unmet protection need, not a sales target.",
            ))
            continue

        premium = product["monthly_premium"]
        pct = (premium / disposable * 100) if disposable > 0 else None
        annual_commission = round(premium * 12 * config.COMMISSION_RATE, 2)
        recs.append(Recommendation(
            status="recommended",
            gap_type=item.type,
            severity_label=item.severity_label,
            product=product,
            rationale=_rationale(item, client, product),
            premium_pct_of_disposable=round(pct, 1) if pct is not None else None,
            projected_annual_commission=annual_commission,
        ))

    return RecommendationResponse(
        client_id=client.client_id,
        disposable_income=round(disposable, 2),
        recommendations=recs,
    )
