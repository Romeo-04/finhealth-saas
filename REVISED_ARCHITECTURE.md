# Revised Solution Architecture — Risk-Informed Financial Health & Insurance Platform

> Working document. Incorporates insights from team discussion on demand-side adoption, bancassurance positioning, and the simplified recommendation model. This supersedes the previous three-layer architecture where Layer 3 was framed around loan-event bundling.

---

## What changed and why

The previous architecture implicitly framed the insurance recommendation as something that happens at the point of loan origination — the farmer comes in to borrow, and the platform tells the loan officer what insurance to attach. That framing was too narrow. It limited the addressable population to active borrowers, made the recommendation contingent on a lending event, and introduced unnecessary complexity around loan product design.

The revised architecture treats insurance recommendation as a **standalone assessment of any FSP client**, triggered by any interaction or on a scheduled basis. The FSP's existing relationship with the client — whether as borrower, depositor, or savings group member — is the channel. The loan is one touchpoint where the recommendation might surface, but it's not the only one and it's not architecturally privileged.

The second major revision is positioning. The Philippine bancassurance market has two tiers that operate on completely different logics, and the platform sits in the gap between them:

- **Commercial bancassurance** (BPI AIA, Manulife China Bank Life, Sun Life Grepa, Allianz PNB Life) — exclusive partnerships between universal banks and global insurers, serving urban middle-class consumers with investment-linked products at PHP 2,000+/month premiums. These institutions already have data infrastructure, customer analytics, and product matching capability. Our platform is redundant here.

- **Microinsurance through MFIs** (CARD MBA model) — compulsory bundling where every borrower gets the same basic life and loan-redemption coverage at ~PHP 60/month. Scaled to 22 million insured individuals. Massively successful at coverage breadth, but coverage is **generic** — everyone gets the same product regardless of whether their specific exposure is to typhoons, drought, health emergencies, or property loss.

The platform brings the **data-driven product matching** of the commercial tier to the **client base** of the microinsurance tier. That is the positioning statement.

---

## The three layers (revised)

### Layer 1 — Data Capture and Standardization

**What it does:** Ingests heterogeneous client data from FSP systems and public sources, normalizes it into a unified client profile.

**What changed:** Nothing structural. This layer was already sound. The only refinement is that the client profile is now explicitly designed to support **any FSP client**, not just borrowers. A depositor-only client will have a thinner profile (no repayment history) but can still be assessed on savings behavior, location-based hazard exposure, livelihood type, and available alternative data.

**Data sources (unchanged):**
- FSP-held records: loan histories, repayment patterns, savings balances, account tenure, livelihood classification, dependents
- BSP-endorsed alternative data: mobile money transaction patterns, utility payment records (where available through open finance or direct FSP integration)
- Government registries: RSBSA (agricultural registry — critical for PCIC eligibility routing), CRDPh (credit risk data for SMEs, live since July 2025 with 33 institutions)
- Public hazard data: GeoRiskPH / HazardHunterPH — typhoon, flood, landslide, earthquake exposure by municipality and barangay
- Existing coverage: any insurance the client already holds (CARD MBA membership, PCIC enrollment, other policies)

**Multi-tenant design (unchanged):** Each FSP tenant's data is logically isolated. The normalization engine maps each institution's idiosyncratic data format to a common schema so the scoring engine sees a consistent input regardless of source institution.

---

### Layer 2 — Multi-Dimensional Financial Health Scoring Engine

**What it does:** Constructs a financial health profile across five dimensions, identifying specific resilience gaps. This is not a credit score.

**What changed:** The core scoring methodology is unchanged, but the framing is sharpened. The previous version described the resilience dimension but didn't make explicit enough how it connects to the recommendation output. The revised version makes the resilience dimension's output a structured **protection gap manifest** — an ordered list of specific, unaddressed risk exposures — that Layer 3 consumes directly.

**The five dimensions:**

1. **Spend** — Does the client's expenditure pattern indicate financial stability? Measured through transaction regularity, expense-to-income ratio, and expense volatility.

2. **Save** — Does the client accumulate buffers? Measured through savings balance trend, savings-to-income ratio, and consistency of deposits.

3. **Borrow** — Does the client use credit sustainably? Measured through repayment timeliness, debt service ratio, and credit utilization trend. (For non-borrower clients, this dimension is either scored from CRDPh data if available, or marked as insufficient-data with appropriate imputation disclosure.)

4. **Plan** — Does the client show evidence of forward-looking financial behavior? Measured through account tenure, product diversification (savings + insurance + credit), and regularity of contributions.

5. **Resilience** — Can the client absorb a shock without financial collapse? This is the load-bearing dimension for the insurance use case. It is constructed from:
   - **Hazard exposure** (GeoRiskPH: what natural disasters threaten this client's location?)
   - **Livelihood vulnerability** (is their income source climate-dependent? seasonal? single-source?)
   - **Existing coverage inventory** (what insurance do they already hold, and what does it actually cover?)
   - **Coverage gap analysis** (given their exposure and their existing coverage, where are they unprotected?)
   - **Shock absorption capacity** (savings buffer relative to estimated loss magnitude from an uninsured event)

**Output of Layer 2:** Per client:
- Overall financial health score (composite of five dimensions, transparently weighted)
- Per-dimension subscores with the raw drivers that produced each
- Health band classification: Healthy / Coping / Vulnerable
- **Protection gap manifest** (new, explicit output): an ordered list of unaddressed risk exposures ranked by severity, each specifying the gap type (crop, calamity, life, health, property, accident), the exposure source (e.g., "client is in a high-typhoon municipality, income is rice farming, no crop or calamity coverage"), and estimated loss magnitude if the risk materializes

**What this is NOT:**
- Not a credit score (does not predict probability of default)
- Not a single opaque model (transparent composite of explainable subscores)
- Not a replacement for CRDPh (CRDPh handles credit risk for SMEs; this handles multi-dimensional financial health for individuals, and the two are complementary — CRDPh data feeds into the Borrow dimension where available)

---

### Layer 3 — Insurance Recommendation Engine

**What it does:** For each client with a protection gap, recommends specific, affordable insurance products matched to their risk profile, from across available providers.

**What changed significantly:**

**1. Decoupled from loan events.** The recommendation is generated for any client with a protection gap, regardless of whether they're currently borrowing. The recommendation surfaces at whatever the next client interaction is — a loan renewal, a deposit visit, a savings group meeting, a scheduled outreach, or a proactive notification to the branch staff. The platform generates the recommendation; the FSP decides when and how to present it.

**2. Multi-provider product matching.** The previous architecture implicitly assumed a single insurer partner. The revised version maintains a **product catalogue spanning multiple providers** — PCIC (government crop insurance), CARD MBA or equivalent mutual benefit association products, CARD Pioneer or equivalent microinsurance products, and any bancassurance partner products the FSP has agreements with. This is directly enabled by BSP's forthcoming revised bancassurance guidelines, which will allow banks to distribute insurance products from multiple providers. The platform matches the client to the best-fit product across the full catalogue, not just one insurer's lineup.

**3. Three-tier adoption mechanism.** The previous version didn't address how the client actually gets covered. The revised version structures recommendations into three tiers based on client cost:

- **Tier A — Free government coverage (zero client cost).** The platform identifies clients who are RSBSA-registered but not enrolled in PCIC crop insurance. PCIC provides 100% premium subsidy for registered farmers covering typhoons, floods, droughts, and pests, yet only about one-third of eligible farmers are actually covered. The platform's recommendation here is pure enrollment routing — the client qualifies for free protection and just needs to be connected to it. This is the strongest, most defensible impact because it removes the affordability objection entirely.

- **Tier B — Embedded microinsurance (minimal incremental cost).** For clients who are FSP members (borrowers or savings group participants), the platform recommends microinsurance products that can be embedded in the existing relationship — either as part of a mutual benefit association membership (the CARD MBA model, ~PHP 60/month) or as a specific microinsurance product within RA 10607 affordability caps (premium capped at 7.5% of daily minimum wage for non-agricultural workers). The cost is real but small, and the channel — the existing FSP relationship — is already in place. The recommendation specifies which product, at what premium, covering what risk, and includes an affordability check against the client's disposable income.

- **Tier C — Targeted commercial microinsurance (affordable but requires a purchasing decision).** For protection gaps not covered by Tier A or B — for example, a client who needs health or property coverage beyond what their mutual benefit association provides — the platform recommends specific products from the FSP's bancassurance partners. These require the client to make an active purchasing decision. The recommendation includes: the specific product, the premium as a percentage of disposable income, the rationale tied to the client's exposure, and the anti-mis-selling check.

**4. Anti-mis-selling rule (unchanged but clarified).** If a genuine protection gap exists but no available product fits within the affordability threshold (monthly premium ≤ 10% of disposable income, within RA 10607 caps where applicable), the platform does not recommend a product. Instead it flags the gap as `protection_gap_unaffordable` so the institution sees the unmet need. This is important both ethically (no one should be pushed into coverage they can't sustain) and for the data story (aggregate unaffordable gaps across the portfolio tell a policy-relevant story about what the market isn't serving).

**5. Group coverage as a use case extension, not core architecture.** For scenarios where a farm owner or cooperative head wants to insure workers or members, the platform can generate a group-level assessment by aggregating individual protection gaps. This is a deployment-level feature, not a change to the scoring engine — the same individual profiles and gap manifests are used, just presented in aggregate with a group policy recommendation. This is not a primary feature for the hackathon demo but worth naming as a v2 capability.

**Recommendation output (per client):**
- Tier classification (A, B, or C)
- Specific product recommendation (name, provider, type, coverage amount, monthly premium)
- Rationale (plain-language explanation referencing the client's specific exposure, e.g., "Rice farmer in Tacloban with no crop or calamity cover. One typhoon season could erase three years of repayment progress. PCIC coverage is available at zero cost because client is RSBSA-registered.")
- Affordability metric (premium as % of disposable income)
- Commission to institution (projected bancassurance commission if the product is adopted — making the incentive explicit and quantifiable)
- Enrollment pathway (what the loan officer or branch staff needs to do: submit PCIC enrollment form, activate MBA membership, or initiate bancassurance application)

---

## Revenue model and incentive alignment

This is the load-bearing insight of the whole architecture and has not changed, but the revised framing makes it cleaner.

**The problem:** Small FSPs have no incentive to invest in client data infrastructure because there's no revenue return. They serve underserved communities out of mandate or mission, but the economics don't support building sophisticated data systems.

**The mechanism:** Bancassurance commissions. Every insurance product adopted through the platform generates commission revenue for the FSP. The platform makes this revenue visible at both the individual level (per-recommendation projected commission) and the portfolio level (aggregate annual commission if all affordable gaps are closed). The FSP sees, concretely, that investing in financial health data infrastructure pays for itself through insurance distribution revenue.

**Why this works structurally:**
- The FSP earns revenue (bancassurance commission)
- The client gets appropriate protection (resilience against shocks)
- The insurer gets distribution reach (last-mile access through FSP branch networks they couldn't build themselves)
- PCIC gets better targeting (closing the two-thirds enrollment gap among eligible farmers)
- The platform is funded by a share of commission revenue (SaaS subscription or revenue-share model), making it self-sustaining

**Why it doesn't work without the data layer:** A loan officer can already recommend insurance without this platform. What they cannot do is systematically identify which of their 500 clients has which specific protection gap, match that gap to the right product from the right provider at the right price, and verify that the recommendation is affordable and appropriate. That assessment is what the platform provides, and it's what makes the commission revenue systematic rather than accidental.

---

## Longitudinal outcome tracking (the feedback loop)

**Unchanged in concept, clarified in role.** The platform tracks, over time, whether clients who adopted recommended coverage show improved financial health scores after shocks compared to clients with similar profiles who remained uninsured. This is the evidence engine that closes the loop:

- For the FSP: demonstrates that insured borrowers default less after disasters (portfolio protection)
- For the client: shows concrete value of coverage (not abstract, but measurable in their own financial trajectory)
- For the system: generates the evidence base that insurance improves financial health outcomes, which is currently absent in the Philippine microinsurance space (GInsure issued 51.4 million policies without tracking financial health outcomes)

This is a v2 feature for production but the hackathon demo simulates it through a 4-quarter simulation with a synthetic shock event at Q3, showing the divergence between protected and unprotected cohorts.

---

## What the loan officer actually sees (UI flow)

**Portfolio view:** KPI bar showing total clients, percentage in each health band, percentage with a protection gap, aggregate uninsured exposure value, and projected annual commission if affordable gaps are closed. Client table below, sortable and filterable, with a resilience-gap flag on each row.

**Client detail view:** The five-dimension radar chart with subscores, the overall score and band, the raw drivers behind each score. Below that, the protection gap manifest: what risks this client is exposed to, what they're currently covered for, and where the gaps are.

**Recommendation panel:** For clients with gaps, the tiered recommendations (A/B/C) with product details, rationale, affordability check, and commission projection. A clear action button for each: "Enroll in PCIC" / "Activate MBA coverage" / "Initiate bancassurance application." For unaffordable gaps, a flagged status with the unmet need visible.

**Outcome tracking view (demo):** The 4-quarter simulation showing how protected vs. unprotected clients diverge after a shock. This is the "why this matters" screen — the evidence that the whole system produces real outcomes.

---

## Honest impact assessment

**Who benefits immediately and concretely:**
- The FSP (commission revenue, portfolio risk reduction, data infrastructure they couldn't afford alone through multi-tenant cost sharing)

**Who benefits meaningfully but indirectly:**
- FSP clients who are enrolled into free PCIC coverage they qualified for but weren't receiving (immediate, zero-cost, measurable)
- FSP clients who adopt microinsurance recommendations and subsequently avoid financial collapse during shocks (real but takes time to materialize and measure)

**Who the platform cannot reach:**
- The unbanked — people with no FSP relationship at all. The platform only works through an existing FSP-client channel. This is a real limitation. The solution helps the banked-but-underserved, not the most vulnerable.

**The tension to name honestly in the pitch:**
- The stakeholder who benefits most immediately is the institution, not the underserved client. That's the point — institutional benefit is the incentive mechanism that makes the system run — but in a hackathon framed around financial health of underserved communities, the pitch must be explicit that institutional benefit is the means, not the end. The end is client resilience.

---

## Positioning against existing solutions

| Solution | What it does | What it doesn't do (our gap) |
|---|---|---|
| CARD MBA | Compulsory life/loan-redemption insurance for all borrowers at ~PHP 60/month | Generic coverage — same product for everyone regardless of specific exposure. No risk-informed matching. No resilience scoring. |
| CARD Pioneer | Non-life microinsurance products (family, hospitalization, group) | Products exist but no systematic process to match the right product to the right client based on assessed risk |
| BPI AIA / Manulife China Bank Life | Sophisticated bancassurance with data-driven matching for urban middle-class | Inaccessible to rural banks and MFIs. Products priced at PHP 2,000+/month. Wrong market segment entirely. |
| CRDPh | Credit risk scoring for SMEs (probability of default) | Credit score only — doesn't construct multi-dimensional financial health or identify protection gaps |
| FinScore / CRIF | Telco-based alternative credit scoring | Same limitation — credit scoring, not health scoring. No resilience dimension. No insurance recommendation. |
| GInsure | Digital microinsurance distribution (51.4M policies) | Distribution without assessment — no financial health profiling, no outcome tracking, no gap analysis |
| PCIC | Free crop insurance for RSBSA farmers | Two-thirds enrollment gap — products exist but targeting and enrollment fail. Our Tier A routing solves this. |

**Our unique position:** We are the only proposed solution that constructs a multi-dimensional financial health profile, identifies specific protection gaps from that profile, matches gaps to appropriate products across multiple providers, and tracks whether coverage actually improves financial health outcomes — all delivered as shared infrastructure small institutions can afford through multi-tenant SaaS.

---

## Hackathon demo scope (Manila, November 2026)

The demo is a vertical slice, not a full product. It shows:

1. Ingest a synthetic rural-FSP dataset (50–100 clients with realistic distributions across livelihoods, locations, income levels, existing coverage)
2. Run Layer 1 normalization
3. Generate Layer 2 financial health profiles with protection gap manifests
4. Surface Layer 3 recommendations across all three tiers (Tier A PCIC routing, Tier B embedded microinsurance, Tier C targeted commercial products)
5. Show the portfolio-level view with aggregate gaps, revenue projections, and commission incentives
6. Run the 4-quarter shock simulation showing the protected-vs-unprotected divergence

The persuasive power is that the full chain runs end to end on one screen — from raw data to actionable recommendation with visible institutional incentive — not as three disconnected tools.

---

## Key regulatory references

- **RA 10607** — Insurance Code of the Philippines. Microinsurance premium caps at 7.5% of daily minimum wage. Defines microinsurance products and distribution channels including bancassurance.
- **RA 10173** — Data Privacy Act. Governs client consent for alternative data use. The platform requires explicit consent and provides imputation transparency disclosure.
- **BSP MORB (Manual of Regulations for Banks)** — Governs bancassurance operations, requires prior BSP approval for partnerships, caps insurance fee income at 30% of total operating income.
- **BSP revised bancassurance guidelines (forthcoming, announced July 2025)** — Will allow banks to offer insurance products from multiple providers, directly enabling the platform's multi-provider matching capability.
- **PCIC / Department of Agriculture** — 100% premium subsidy for RSBSA-registered farmers. 2026 budget PHP 6.5B. Coverage up to PHP 25,000/ha for rice/corn.
- **CRDPh** — BSP-JICA credit risk database, live July 2025 with 33 participating institutions. Complementary to (not replaced by) the financial health score.
