# FinHealth Platform (Demo)

A runnable proof-of-concept of a **risk-informed financial health & insurance platform** for
rural banks and microfinance institutions (MFIs) in the Philippines. A loan officer opens a
client and sees a multi-dimensional **financial health profile** (not a credit score), exactly
**where the client is dangerously underinsured relative to real-world exposure**, and an
**explainable, affordable insurance recommendation** — while the institution sees the aggregate
portfolio picture and the commission incentive that makes serving these clients sustainable.

**All data is synthetic.** No real personal data exists anywhere in this repository.

## Quick start

Backend (from `backend/`):

```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Frontend (from `frontend/`):

```
npm install
npm run dev
```

Open http://localhost:5173. The backend auto-seeds **150 synthetic clients** (seeded RNG,
reproducible) into a local SQLite file on first start. API docs at http://localhost:8000/docs.

## Architecture — three layers mapping to three problems

**Layer 1 — ingestion & standardization** (`app/layer1_ingest.py`) → *the fragmented-data
problem.* A canonical client schema (`app/schema.py`) that a fragmented rural FSP could
realistically populate: identity/context, 12 months of income, expenses & savings, loans &
repayment history, insurance held, prior shocks. CSV ingestion deduplicates, normalizes,
validates, and returns a validation report. Missing non-critical fields are imputed with
conservative defaults and **flagged** (`imputed_fields`) — never silently filled.

**Layer 2 — financial health scoring engine** (`app/layer2_scoring.py`) → *the credit-only
evaluation problem.* Four explainable dimension subscores (0–100), each returning its
**drivers** (the raw values and benchmark comparisons that produced the number):

1. **Income stability** — coefficient of variation of monthly inflows, diversity bonus,
   negative-trend penalty. An optional, clearly labelled **ML-assisted refinement**
   (GradientBoostingRegressor) blends in at 25% weight for this one subscore only; the
   rule-based score stands alone if the model is absent.
2. **Savings & liquidity** — months of essential expenses covered, mapped to the established
   financial-health benchmark (<1 month → 0–40 … ≥6 months → 90–100).
3. **Debt burden** — debt-service ratio bands, scaled by repayment history, with a
   concurrent-loan penalty.
4. **Resilience & protection** — the distinctive dimension: a required-protection set is
   derived from actual exposure (hazard zone → calamity/property; farming/fishing → crop;
   dependents → life; everyone → health), severity-weighted, and compared with what the client
   holds. The unmet remainder is the **resilience gap**.

The overall score is a **transparent weighted composite** (equal weights, configurable in
`app/config.py`) — there is deliberately no top-level model. Bands: Healthy ≥ 70,
Coping 40–69, Vulnerable < 40. Each profile also carries a `proxy_credit_signal` built only
from repayment history and DSR, so the UI can show clients who **look fine on a credit proxy
yet are Vulnerable on financial health** (e.g. seeded client `C0011`: credit proxy 93,
FinHealth 38 — perfect repayment, but seasonal income, no savings buffer, full typhoon
exposure, zero protection).

**Layer 3 — risk-informed recommendation** (`app/layer3_recommend.py`) → *the resilience &
incentive gap.* Walks the resilience gap in severity order and matches each missing protection
to the best-fit product from a synthetic 10-product microinsurance catalogue
(`app/data/products.json`). Guardrails:

- **Affordability:** premium ≤ 10% of monthly disposable income **and** under a microinsurance
  cap (modelling the RA 10607 idea that premiums stay small relative to the daily minimum wage).
- **Anti-mis-selling:** a genuine gap with no affordable product returns
  `protection_gap_unaffordable` — the unmet need is surfaced to the institution; the client is
  never pushed into a product they cannot sustain.

Every recommendation carries an exposure-specific plain-language rationale, the premium as a %
of disposable income, and the **projected commission** to the institution (20% of annual
premium, configurable) — the incentive made explicit, portfolio-wide on the dashboard.

**Longitudinal tracking** (`app/tracking.py`): `POST /simulate` runs 4 quarters over the real
scoring engine, injecting a typhoon at Q3 against all typhoon/flood-zone clients. Clients with
calamity/crop cover absorb a small hit and recover by Q4; unprotected clients drop sharply and
stay low — the outcome evidence that protection improves resilience.

## API

| Endpoint | Purpose |
|---|---|
| `POST /seed` | (Re)generate the synthetic dataset (also runs on startup) |
| `POST /ingest` | Upload CSV in the canonical schema → validation report |
| `GET /clients` | Summaries: score, band, gap flag, credit proxy |
| `GET /clients/{id}` | Full profile: 4 subscores + drivers, gap, proxy signal |
| `GET /clients/{id}/recommendations` | Layer 3 output with rationales & commission |
| `GET /portfolio` | Dashboard KPIs incl. projected commission if gaps closed |
| `POST /simulate` | 4-quarter shock simulation, protected vs unprotected cohorts |

## Responsible-AI properties

- **Explainability everywhere:** no score appears without its drivers; the overall score is a
  transparent composite; the only ML is a labelled sub-component refinement.
- **Imputation transparency:** imputed fields are flagged on the record and shown in the UI.
- **Affordability guardrail + anti-mis-selling:** unaffordable genuine gaps are flagged, not sold.
- **Synthetic data only**, seeded and reproducible.
- **Human-in-the-loop:** the UI frames recommendations as loan-officer decision support, not
  automated decisions.

## Assumptions (stated, not hidden)

- "Months of savings" benchmark bands follow the common financial-health practice
  (3+ months = resilient).
- Asset-holding livelihoods (store, tricycle, vendor, boat, farm) are treated as having
  insurable property when in a hazard zone.
- Clients with no loan history get `on_time_ratio` imputed to 1.0 (no penalty for thin files)
  — and the imputation is flagged.
- The microinsurance premium cap is modelled at ₱650/month (~one NCR daily minimum wage).
- Commission is a flat 20% of annual premium; real bancassurance splits vary by product.

Tuning knobs (weights, bands, caps, shock magnitudes) all live in `backend/app/config.py`.
`backend/smoke_test.py` re-checks the acceptance criteria end-to-end offline.
