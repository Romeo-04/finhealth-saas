"""
Canonical data model.

The SQLModel `Client` table is the single standardized schema that Layer 1
normalizes everything into. List/JSON-shaped fields (monthly income series,
loans, insurance held, imputed-field flags) are stored as JSON strings in
SQLite and exposed as typed lists through the pydantic response models.

All data is synthetic. No real PII exists anywhere in this repository.
"""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

HAZARD_ZONES = ("typhoon", "flood", "low_risk")
LIVELIHOODS = (
    "rice_farming",
    "fishing",
    "sari_sari_store",
    "tricycle_driver",
    "market_vendor",
    "salaried",
)
INSURANCE_TYPES = ("life", "health", "crop", "calamity", "property", "accident")


class Client(SQLModel, table=True):
    """Standardized client record (output of Layer 1)."""

    client_id: str = Field(primary_key=True)
    name: str
    municipality: str
    hazard_zone: str  # typhoon | flood | low_risk
    livelihood: str
    household_dependents: int

    # JSON-encoded list of 12 monthly inflows
    monthly_income_json: str
    income_sources: int

    monthly_essential_expenses: float          # mean/benchmark essential expenses
    # JSON-encoded list of 12 monthly essential-expense outflows (Spend dimension).
    # Derived as a flat series from the scalar when a series isn't provided.
    monthly_expenses_json: str = "[]"
    liquid_savings: float

    # JSON-encoded list of {principal, monthly_payment, months_remaining}.
    # Empty for non-borrower clients (depositor / savings-group members).
    loans_json: str
    on_time_ratio: float  # 0-1 repayment history

    # Forward-looking (Plan) signals.
    account_tenure_months: int = 0
    savings_deposit_regularity: float = 0.0    # 0-1 consistency of deposits

    # Government-registry linkage — RSBSA registration gates Tier-A PCIC routing.
    rsbsa_registered: bool = False

    # JSON-encoded list of insurance types held
    insurance_held_json: str
    prior_shock_last_24m: bool

    # JSON-encoded list of field names that Layer 1 imputed (never silent)
    imputed_fields_json: str = "[]"

    # -- typed accessors -----------------------------------------------------
    @property
    def monthly_income(self) -> list[float]:
        return json.loads(self.monthly_income_json)

    @property
    def monthly_expenses(self) -> list[float]:
        series = json.loads(self.monthly_expenses_json or "[]")
        if not series:
            # Fall back to a flat series from the scalar benchmark.
            return [self.monthly_essential_expenses] * 12
        return series

    @property
    def loans(self) -> list[dict]:
        return json.loads(self.loans_json)

    @property
    def insurance_held(self) -> list[str]:
        return json.loads(self.insurance_held_json)

    @property
    def imputed_fields(self) -> list[str]:
        return json.loads(self.imputed_fields_json)


# ---------------------------------------------------------------------------
# API response shapes (documented, typed JSON)
# ---------------------------------------------------------------------------

class Driver(BaseModel):
    """One explainability driver behind a subscore."""
    label: str
    detail: str
    raw_value: float | str


class DimensionScore(BaseModel):
    score: int
    drivers: list[Driver]
    ml_assisted: bool = False       # true only for the labelled ML refinement
    insufficient_data: bool = False  # true when the dimension can't be assessed


class GapItem(BaseModel):
    type: str
    severity: int            # numeric severity weight
    severity_label: str      # "high" | "medium"
    reason: str              # plain-language exposure reason
    estimated_loss: float = 0.0  # est. peso loss if this risk materializes


class HealthProfile(BaseModel):
    client_id: str
    name: str
    municipality: str
    hazard_zone: str
    livelihood: str
    household_dependents: int
    overall_score: int
    band: str
    dimensions: dict[str, DimensionScore]
    resilience_gap: list[GapItem]
    proxy_credit_signal: int
    proxy_credit_band: str
    imputed_fields: list[str]
    mean_monthly_income: float
    monthly_essential_expenses: float
    liquid_savings: float
    monthly_debt_service: float
    insurance_held: list[str]
    monthly_income: list[float]
    account_tenure_months: int
    rsbsa_registered: bool
    is_borrower: bool


class ClientSummary(BaseModel):
    client_id: str
    name: str
    municipality: str
    hazard_zone: str
    livelihood: str
    overall_score: int
    band: str
    has_resilience_gap: bool
    proxy_credit_signal: int


class Recommendation(BaseModel):
    status: str  # "recommended" | "protection_gap_unaffordable"
    gap_type: str
    severity_label: str
    tier: Optional[str] = None            # "A" | "B" | "C"
    tier_label: Optional[str] = None      # human-readable tier description
    product: Optional[dict] = None
    rationale: str
    premium_pct_of_disposable: Optional[float] = None
    projected_annual_commission: Optional[float] = None
    enrollment_pathway: Optional[str] = None  # what branch staff must do


class RecommendationResponse(BaseModel):
    client_id: str
    disposable_income: float
    recommendations: list[Recommendation]
    note: str = (
        "Decision support for the loan officer — not an automated decision. "
        "Review with the client before any enrolment."
    )


class ValidationReport(BaseModel):
    records_received: int
    records_ingested: int
    records_rejected: int
    rejection_reasons: list[str]
    fields_imputed: dict[str, int]  # field name -> count of records imputed


class PortfolioStats(BaseModel):
    total_clients: int
    band_counts: dict[str, int]
    band_pct: dict[str, float]
    pct_with_resilience_gap: float
    aggregate_uninsured_exposure: float
    projected_annual_commission: float
