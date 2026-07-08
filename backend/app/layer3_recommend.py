"""
Layer 3 — risk-informed insurance recommendation (three-tier adoption model).

Takes the ordered protection-gap manifest from Layer 2 and matches each missing
protection type to the best-fit product using the revised architecture's
three-tier adoption mechanism, in priority order:

  Tier A — Free government coverage (zero client cost). RSBSA-registered farmers
           not enrolled in PCIC are routed to free crop coverage. Strongest,
           most defensible fix because it removes the affordability objection.
  Tier B — Embedded microinsurance (minimal cost) via existing FSP / MBA
           membership (the CARD MBA / CARD Pioneer model).
  Tier C — Targeted commercial microinsurance from a bancassurance partner,
           requiring the client's active purchasing decision.

Two guardrails are unchanged:
  1. Affordability: premium <= 10% of monthly disposable income AND within the
     microinsurance cap (modelling RA 10607). Tier A is free, so always passes.
  2. Anti-mis-selling: if a genuine gap exists but no tier yields a sustainable
     product, return `protection_gap_unaffordable` — surface the unmet need,
     never push a product the client cannot sustain.

Institution commission is computed and shown explicitly. Tier A (government)
generates no commission — an honest signal that the free fix has no revenue
kicker but is still the right recommendation.
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

TIER_LABEL = {
    "A": "Free government coverage",
    "B": "Embedded microinsurance",
    "C": "Targeted commercial",
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


def _eligible(product: dict, client: Client) -> bool:
    """Livelihood / registry gating for a product."""
    ev = product.get("eligible_livelihoods")
    if ev and client.livelihood not in ev:
        return False
    if product.get("requires_rsbsa") and not client.rsbsa_registered:
        return False
    return True


def _best_fit_product(gap_type: str, client: Client,
                      disposable: float) -> tuple[dict | None, str | None]:
    """Best-fit product for a gap, honouring tier priority (A -> B -> C). Within
    a tier, prefer the most coverage per peso of premium. Returns (product, tier)
    or (None, None) if nothing eligible and affordable exists in any tier."""
    by_type = [p for p in load_products()
               if p["type"] == gap_type and _eligible(p, client)]
    for tier in ("A", "B", "C"):
        tier_products = [p for p in by_type if p["tier"] == tier]
        affordable = [p for p in tier_products
                      if tier == "A" or _is_affordable(p["monthly_premium"], disposable)]
        if affordable:
            product = max(affordable,
                          key=lambda p: p["coverage_amount"] / max(p["monthly_premium"], 1))
            return product, tier
    return None, None


def _enrollment_pathway(tier: str, product: dict) -> str:
    provider = product["provider"]
    if tier == "A":
        return ("Submit the PCIC enrollment form for this RSBSA-registered client — "
                "100% premium subsidy, zero cost to the client.")
    if tier == "B":
        return (f"Activate {provider} coverage through the client's existing FSP "
                f"membership (embedded microinsurance).")
    return (f"Initiate a bancassurance application with {provider} — requires the "
            f"client's active enrolment and first premium.")


def _rationale(gap: GapItem, client: Client, product: dict | None, tier: str | None) -> str:
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
    base = (f"{who} in {client.municipality}: {exposure_clause}, with no {gap.type} "
            f"cover — {consequence} (est. exposure ₱{gap.estimated_loss:,.0f}).")
    if not product:
        return base
    if tier == "A":
        return (f"{base} {product['name']} closes this gap at ZERO cost: the client is "
                f"RSBSA-registered and qualifies for PCIC's 100% premium subsidy "
                f"(₱{product['coverage_amount']:,.0f} of cover).")
    return (f"{base} {product['name']} closes this gap with "
            f"₱{product['coverage_amount']:,.0f} of cover for "
            f"₱{product['monthly_premium']:,.0f}/month.")


def recommend(client: Client, gap: list[GapItem]) -> RecommendationResponse:
    disposable = disposable_income(client)
    recs: list[Recommendation] = []

    for item in gap:  # already ordered highest severity first by Layer 2
        product, tier = _best_fit_product(item.type, client, disposable)
        if product is None:
            recs.append(Recommendation(
                status="protection_gap_unaffordable",
                gap_type=item.type,
                severity_label=item.severity_label,
                product=None,
                rationale=_rationale(item, client, None, None) +
                " No catalogue product across Tiers A–C fits within 10% of this "
                "client's disposable income — flagged as an unmet protection need, "
                "not a sales target.",
            ))
            continue

        premium = product["monthly_premium"]
        pct = (premium / disposable * 100) if disposable > 0 else (0.0 if premium == 0 else None)
        # Tier A is government coverage — no institutional commission.
        annual_commission = (0.0 if tier == "A"
                             else round(premium * 12 * config.COMMISSION_RATE, 2))
        recs.append(Recommendation(
            status="recommended",
            gap_type=item.type,
            severity_label=item.severity_label,
            tier=tier,
            tier_label=TIER_LABEL[tier],
            product=product,
            rationale=_rationale(item, client, product, tier),
            premium_pct_of_disposable=round(pct, 1) if pct is not None else None,
            projected_annual_commission=annual_commission,
            enrollment_pathway=_enrollment_pathway(tier, product),
        ))

    return RecommendationResponse(
        client_id=client.client_id,
        disposable_income=round(disposable, 2),
        recommendations=recs,
    )
