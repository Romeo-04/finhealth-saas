"""
Layer 1 — data ingestion and standardization.

Accepts records (from the synthetic generator or an uploaded CSV), then:
- deduplicates on client_id (first occurrence wins),
- normalizes types (numeric coercion, JSON list parsing),
- validates against the canonical schema (rows missing critical identity or
  income data are rejected with a reason),
- imputes ONLY safe defaults for non-critical fields, and FLAGS every imputed
  field on the record (`imputed_fields`) — never silently fills.

Returns standardized `Client` rows plus a `ValidationReport`.
"""
from __future__ import annotations

import csv
import io
import json
from collections import Counter

from sqlmodel import Session, delete

from . import config
from .schema import Client, HAZARD_ZONES, INSURANCE_TYPES, LIVELIHOODS, ValidationReport

# Fields without which a record is meaningless and must be rejected.
CRITICAL_FIELDS = ["client_id", "monthly_income", "monthly_essential_expenses"]

# Non-critical fields we may impute, with their conservative defaults.
IMPUTABLE_DEFAULTS = {
    "name": lambda r: f"Client {r.get('client_id', '?')}",
    "municipality": lambda r: "Unknown",
    "hazard_zone": lambda r: "low_risk",      # conservative: do not invent exposure
    "livelihood": lambda r: "market_vendor",
    "household_dependents": lambda r: 0,
    "income_sources": lambda r: 1,
    "liquid_savings": lambda r: 0.0,           # conservative: assume no buffer
    "loans": lambda r: [],
    "on_time_ratio": lambda r: 1.0,            # no history -> do not penalize
    "insurance_held": lambda r: [],
    "prior_shock_last_24m": lambda r: False,
}


def _parse_list(value, expected_type=float):
    """Accept a real list or a JSON-encoded string list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    raise ValueError(f"not a list: {value!r}")


def standardize_records(raw_records: list[dict]) -> tuple[list[Client], ValidationReport]:
    seen_ids: set[str] = set()
    clients: list[Client] = []
    rejections: list[str] = []
    imputed_counter: Counter = Counter()

    for idx, raw in enumerate(raw_records):
        row_ref = raw.get("client_id") or f"row {idx + 1}"
        imputed: list[str] = []

        # ---- critical validation ----------------------------------------
        missing = [f for f in CRITICAL_FIELDS
                   if raw.get(f) in (None, "", [])]
        if missing:
            rejections.append(f"{row_ref}: missing critical field(s) {missing}")
            continue

        client_id = str(raw["client_id"]).strip()
        if client_id in seen_ids:
            rejections.append(f"{client_id}: duplicate client_id (kept first occurrence)")
            continue

        try:
            income = [float(x) for x in _parse_list(raw["monthly_income"])]
            expenses = float(raw["monthly_essential_expenses"])
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            rejections.append(f"{client_id}: unparseable income/expenses ({exc})")
            continue

        if len(income) != 12:
            rejections.append(f"{client_id}: monthly_income must have 12 values, got {len(income)}")
            continue
        if expenses <= 0 or min(income) < 0:
            rejections.append(f"{client_id}: non-positive expenses or negative income")
            continue

        # ---- impute non-critical fields, flagging each --------------------
        record = dict(raw)
        for field, default_fn in IMPUTABLE_DEFAULTS.items():
            if record.get(field) in (None, ""):
                record[field] = default_fn(record)
                imputed.append(field)
                imputed_counter[field] += 1

        # ---- normalize types & enums -------------------------------------
        try:
            loans = _parse_list(record["loans"]) if record["loans"] else []
            held = _parse_list(record["insurance_held"]) if record["insurance_held"] else []
        except (ValueError, json.JSONDecodeError) as exc:
            rejections.append(f"{client_id}: unparseable loans/insurance ({exc})")
            continue

        hazard = str(record["hazard_zone"]).strip().lower()
        if hazard not in HAZARD_ZONES:
            hazard = "low_risk"
            imputed.append("hazard_zone")
            imputed_counter["hazard_zone"] += 1
        livelihood = str(record["livelihood"]).strip().lower()
        if livelihood not in LIVELIHOODS:
            livelihood = "market_vendor"
            imputed.append("livelihood")
            imputed_counter["livelihood"] += 1
        held = [h for h in held if h in INSURANCE_TYPES]

        prior_shock = record["prior_shock_last_24m"]
        if isinstance(prior_shock, str):
            prior_shock = prior_shock.strip().lower() in ("true", "1", "yes")

        clients.append(Client(
            client_id=client_id,
            name=str(record["name"]),
            municipality=str(record["municipality"]),
            hazard_zone=hazard,
            livelihood=livelihood,
            household_dependents=int(float(record["household_dependents"])),
            monthly_income_json=json.dumps(income),
            income_sources=int(float(record["income_sources"])),
            monthly_essential_expenses=expenses,
            liquid_savings=float(record["liquid_savings"]),
            loans_json=json.dumps(loans),
            on_time_ratio=min(1.0, max(0.0, float(record["on_time_ratio"]))),
            insurance_held_json=json.dumps(sorted(set(held))),
            prior_shock_last_24m=bool(prior_shock),
            imputed_fields_json=json.dumps(sorted(set(imputed))),
        ))
        seen_ids.add(client_id)

    report = ValidationReport(
        records_received=len(raw_records),
        records_ingested=len(clients),
        records_rejected=len(rejections),
        rejection_reasons=rejections,
        fields_imputed=dict(imputed_counter),
    )
    return clients, report


def ingest_csv(csv_bytes: bytes, session: Session, replace: bool = False) -> ValidationReport:
    """Parse an uploaded CSV (list fields JSON-encoded in cells), standardize,
    and persist. With replace=True the table is cleared first."""
    text = csv_bytes.decode("utf-8-sig")
    raw_records = list(csv.DictReader(io.StringIO(text)))
    clients, report = standardize_records(raw_records)

    if replace:
        session.exec(delete(Client))
    for c in clients:
        session.merge(c)  # upsert on client_id
    session.commit()
    return report


def seed_database(session: Session, force: bool = False) -> ValidationReport:
    """Generate synthetic clients and persist them (idempotent unless force)."""
    from .data.synthetic_generator import generate_clients

    existing = session.exec(Client.__table__.select().limit(1)).first()
    if existing and not force:
        return ValidationReport(records_received=0, records_ingested=0,
                                records_rejected=0, rejection_reasons=[],
                                fields_imputed={})

    raw = generate_clients(config.SYNTHETIC_CLIENT_COUNT, config.RANDOM_SEED)
    clients, report = standardize_records(raw)
    session.exec(delete(Client))
    for c in clients:
        session.add(c)
    session.commit()
    return report
