"""
Longitudinal outcome tracking — the feedback loop no FSP currently runs.

Simulates 4 quarters for clients in typhoon/flood zones. At Q3 a typhoon hits:
income and savings drop. Clients holding (or assumed to have adopted) the
relevant calamity/crop protection absorb a much smaller hit and recover by Q4;
unprotected clients drop sharply and stay low.

The simulation re-runs the REAL Layer 2 engine on perturbed copies of each
client each quarter — the trajectories are produced by the actual scoring
logic, not hand-drawn numbers.
"""
from __future__ import annotations

import copy
import json
import statistics

from . import config
from .layer2_scoring import band_for, build_profile

BANDS = ("Healthy", "Coping", "Vulnerable")


def _perturbed_client(client, income_factor: float, savings_factor: float):
    """Shallow-copy a client with scaled income series and savings."""
    clone = copy.copy(client)
    income = [round(m * income_factor, 2) for m in client.monthly_income]
    clone.monthly_income_json = json.dumps(income)
    clone.liquid_savings = round(client.liquid_savings * savings_factor, 2)
    return clone


def _band_distribution(scores: list[int]) -> dict[str, int]:
    dist = {b: 0 for b in BANDS}
    for s in scores:
        dist[band_for(s)] += 1
    return dist


def run_simulation(clients: list, ml_model=None) -> dict:
    """Returns per-quarter band distributions and mean scores for the
    protected vs unprotected cohorts in the shock-affected zones."""
    affected = [c for c in clients if c.hazard_zone in ("typhoon", "flood")]
    protected = [c for c in affected
                 if {"calamity", "crop"} & set(c.insurance_held)]
    unprotected = [c for c in affected
                   if not ({"calamity", "crop"} & set(c.insurance_held))]

    def cohort_trajectory(cohort, is_protected: bool):
        if is_protected:
            shock_income = 1 - config.SHOCK_INCOME_DROP_PROTECTED
            shock_savings = 1 - config.SHOCK_SAVINGS_DRAIN_PROTECTED
            recovery = config.RECOVERY_RATE_PROTECTED
        else:
            shock_income = 1 - config.SHOCK_INCOME_DROP_UNPROTECTED
            shock_savings = 1 - config.SHOCK_SAVINGS_DRAIN_UNPROTECTED
            recovery = config.RECOVERY_RATE_UNPROTECTED

        quarters = []
        for q in range(1, 5):
            if q < config.SHOCK_QUARTER:
                income_f, savings_f = 1.0, 1.0
            elif q == config.SHOCK_QUARTER:
                income_f, savings_f = shock_income, shock_savings
            else:  # post-shock quarter: recover a share of what was lost
                income_f = shock_income + recovery * (1.0 - shock_income)
                savings_f = shock_savings + recovery * (1.0 - shock_savings)

            scores = [build_profile(_perturbed_client(c, income_f, savings_f),
                                    ml_model).overall_score
                      for c in cohort]
            quarters.append({
                "quarter": f"Q{q}",
                "shock": q == config.SHOCK_QUARTER,
                "mean_score": round(statistics.mean(scores), 1) if scores else 0,
                "band_distribution": _band_distribution(scores),
            })
        return quarters

    return {
        "shock_quarter": f"Q{config.SHOCK_QUARTER}",
        "shock_description": (
            "Simulated typhoon hits all typhoon/flood-zone clients in Q3. "
            "Protected = holds calamity or crop cover; unprotected = holds neither."
        ),
        "affected_clients": len(affected),
        "cohorts": {
            "protected": {
                "size": len(protected),
                "trajectory": cohort_trajectory(protected, True),
            },
            "unprotected": {
                "size": len(unprotected),
                "trajectory": cohort_trajectory(unprotected, False),
            },
        },
    }
