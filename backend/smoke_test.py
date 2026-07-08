"""Offline smoke test: seeds the DB, scores all clients, checks acceptance
criteria from the build spec, and exercises recommendations + simulation."""
import statistics

from sqlmodel import Session, SQLModel, create_engine, select

from app.layer1_ingest import seed_database
from app.layer2_scoring import build_profile, train_income_ml_model
from app.layer3_recommend import recommend
from app.tracking import run_simulation
from app.schema import Client

engine = create_engine("sqlite:///smoke_test.db")
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    report = seed_database(session, force=True)
    print(f"Seeded: {report.records_ingested} clients, rejected {report.records_rejected}")
    assert report.records_ingested >= 140

    clients = session.exec(select(Client)).all()
    ml = train_income_ml_model(clients)
    print(f"ML model trained: {ml is not None}")

    profiles = [build_profile(c, ml) for c in clients]

    bands = {"Healthy": 0, "Coping": 0, "Vulnerable": 0}
    for p in profiles:
        bands[p.band] += 1
        assert 0 <= p.overall_score <= 100
        for name, dim in p.dimensions.items():
            assert dim.drivers, f"{p.client_id} {name} has no drivers"
    print(f"Bands: {bands}")

    with_gap = sum(1 for p in profiles if p.resilience_gap)
    print(f"Clients with resilience gap: {with_gap}/{len(profiles)} ({100*with_gap/len(profiles):.0f}%)")
    assert with_gap > len(profiles) / 2, "majority must have a gap"

    divergent = [p for p in profiles
                 if p.proxy_credit_signal >= 70 and p.band == "Vulnerable"]
    print(f"Credit-vs-health divergence cases (proxy>=70 but Vulnerable): {len(divergent)}")
    for p in divergent[:3]:
        print(f"  {p.client_id} {p.name}: proxy={p.proxy_credit_signal}, "
              f"health={p.overall_score}, {p.livelihood}/{p.hazard_zone}")
    assert divergent, "need at least one divergence case"

    # Non-borrower handling: Borrow dimension must be insufficient-data and
    # excluded from the composite for depositor-only clients.
    non_borrowers = [c for c in clients if not c.loans]
    print(f"Non-borrower (depositor-only) clients: {len(non_borrowers)}")
    assert non_borrowers, "expected some non-borrower clients"
    nbp = build_profile(non_borrowers[0], ml)
    assert nbp.dimensions["borrow"].insufficient_data, "Borrow must be insufficient-data"
    assert not nbp.is_borrower

    # Estimated loss must be quantified on every gap item.
    for p in profiles:
        for g in p.resilience_gap:
            assert g.estimated_loss > 0, f"{p.client_id} {g.type} has no estimated loss"

    # Recommendations for a few gapped clients — three-tier adoption model.
    recommended = unaffordable = 0
    tiers = {"A": 0, "B": 0, "C": 0}
    for c in clients:
        p = next(x for x in profiles if x.client_id == c.client_id)
        if not p.resilience_gap:
            continue
        resp = recommend(c, p.resilience_gap)
        for r in resp.recommendations:
            if r.status == "recommended":
                recommended += 1
                assert r.tier in ("A", "B", "C")
                tiers[r.tier] += 1
                assert r.premium_pct_of_disposable is not None
                assert r.premium_pct_of_disposable <= 10.001
                assert r.projected_annual_commission >= 0  # Tier A is free -> 0
                assert r.enrollment_pathway
            else:
                unaffordable += 1
    print(f"Recommendations: {recommended} recommended, {unaffordable} flagged unaffordable")
    print(f"  by tier — A (free PCIC): {tiers['A']}, B (embedded): {tiers['B']}, C (commercial): {tiers['C']}")
    assert recommended > 0 and unaffordable > 0
    assert tiers["A"] > 0, "expected some free Tier-A (PCIC) routings"

    # Example rationale
    sample = next(c for c in clients if c.client_id == "C0011")
    sp = build_profile(sample, ml)
    sr = recommend(sample, sp.resilience_gap)
    print(f"\nSample divergence client C0011: health={sp.overall_score} ({sp.band}), "
          f"proxy={sp.proxy_credit_signal} ({sp.proxy_credit_band})")
    for r in sr.recommendations[:2]:
        print(f"  [{r.status}] {r.gap_type}: {r.rationale[:140]}")

    # Simulation
    sim = run_simulation(clients, ml)
    prot = sim["cohorts"]["protected"]["trajectory"]
    unprot = sim["cohorts"]["unprotected"]["trajectory"]
    print(f"\nSimulation — protected n={sim['cohorts']['protected']['size']}, "
          f"unprotected n={sim['cohorts']['unprotected']['size']}")
    print("  Q  protected_mean  unprotected_mean")
    for pq, uq in zip(prot, unprot):
        print(f"  {pq['quarter']}  {pq['mean_score']:>8}        {uq['mean_score']:>8}"
              + ("   <- SHOCK" if pq["shock"] else ""))
    q2u, q3u = unprot[1]["mean_score"], unprot[2]["mean_score"]
    q3p_drop = prot[1]["mean_score"] - prot[2]["mean_score"]
    assert q2u - q3u > q3p_drop, "unprotected must drop more at shock"
    assert unprot[3]["mean_score"] < prot[3]["mean_score"], "protected must end higher"

print("\nALL SMOKE TESTS PASSED")
