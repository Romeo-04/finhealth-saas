"""
FastAPI app — wires Layers 1-3 plus the longitudinal simulation.

Run:  uvicorn app.main:app --reload --port 8000   (from backend/)
The SQLite DB is seeded with ~150 synthetic clients automatically on startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel, create_engine, select

from . import config
from .layer1_ingest import ingest_csv, seed_database
from .layer2_scoring import build_profile, train_income_ml_model
from .layer3_recommend import disposable_income, load_products, recommend
from .schema import (Client, ClientSummary, HealthProfile, PortfolioStats,
                     RecommendationResponse, ValidationReport)
from .tracking import run_simulation

DB_PATH = Path(__file__).resolve().parent.parent / "finhealth.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False,
                       connect_args={"check_same_thread": False})

# Trained once at startup; used only inside the labelled income-stability
# refinement. The engine works without it.
ML_MODEL = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ML_MODEL
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        report = seed_database(session)
        if report.records_ingested:
            print(f"Seeded {report.records_ingested} synthetic clients.")
        clients = session.exec(select(Client)).all()
        ML_MODEL = train_income_ml_model(clients)
    yield


app = FastAPI(title="FinHealth Platform (Demo)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _all_clients(session: Session) -> list[Client]:
    return session.exec(select(Client)).all()


@app.post("/seed", response_model=ValidationReport)
def seed(force: bool = True):
    """(Re)generate the synthetic dataset."""
    global ML_MODEL
    with Session(engine) as session:
        report = seed_database(session, force=force)
        ML_MODEL = train_income_ml_model(_all_clients(session))
    return report


@app.post("/ingest", response_model=ValidationReport)
async def ingest(file: UploadFile, replace: bool = False):
    """Layer 1: accept a CSV in the canonical schema (list fields JSON-encoded
    per cell) and return the validation report."""
    content = await file.read()
    with Session(engine) as session:
        return ingest_csv(content, session, replace=replace)


@app.get("/clients", response_model=list[ClientSummary])
def list_clients():
    with Session(engine) as session:
        summaries = []
        for c in _all_clients(session):
            p = build_profile(c, ML_MODEL)
            summaries.append(ClientSummary(
                client_id=p.client_id, name=p.name,
                municipality=p.municipality, hazard_zone=p.hazard_zone,
                livelihood=p.livelihood, overall_score=p.overall_score,
                band=p.band, has_resilience_gap=len(p.resilience_gap) > 0,
                proxy_credit_signal=p.proxy_credit_signal,
            ))
        summaries.sort(key=lambda s: s.overall_score)
        return summaries


@app.get("/clients/{client_id}", response_model=HealthProfile)
def client_detail(client_id: str):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client:
            raise HTTPException(404, f"client {client_id} not found")
        return build_profile(client, ML_MODEL)


@app.get("/clients/{client_id}/recommendations", response_model=RecommendationResponse)
def client_recommendations(client_id: str):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client:
            raise HTTPException(404, f"client {client_id} not found")
        profile = build_profile(client, ML_MODEL)
        return recommend(client, profile.resilience_gap)


@app.get("/portfolio", response_model=PortfolioStats)
def portfolio():
    with Session(engine) as session:
        clients = _all_clients(session)
        if not clients:
            raise HTTPException(404, "no clients — POST /seed first")

        band_counts = {"Healthy": 0, "Coping": 0, "Vulnerable": 0}
        with_gap = 0
        uninsured_exposure = 0.0
        projected_commission = 0.0
        products = load_products()
        cheapest_cover = {}  # type -> coverage_amount of best value product
        for p in products:
            cur = cheapest_cover.get(p["type"])
            if cur is None or p["coverage_amount"] > cur:
                cheapest_cover[p["type"]] = p["coverage_amount"]

        for c in clients:
            profile = build_profile(c, ML_MODEL)
            band_counts[profile.band] += 1
            if profile.resilience_gap:
                with_gap += 1
                # Aggregate uninsured exposure: the cover value the portfolio
                # is missing across all gap types.
                uninsured_exposure += sum(
                    cheapest_cover.get(g.type, 0) for g in profile.resilience_gap)
                recs = recommend(c, profile.resilience_gap)
                projected_commission += sum(
                    r.projected_annual_commission or 0
                    for r in recs.recommendations if r.status == "recommended")

        n = len(clients)
        return PortfolioStats(
            total_clients=n,
            band_counts=band_counts,
            band_pct={b: round(100 * v / n, 1) for b, v in band_counts.items()},
            pct_with_resilience_gap=round(100 * with_gap / n, 1),
            aggregate_uninsured_exposure=round(uninsured_exposure, 2),
            projected_annual_commission=round(projected_commission, 2),
        )


@app.post("/simulate")
def simulate():
    """Run the 4-quarter longitudinal shock simulation (typhoon at Q3)."""
    with Session(engine) as session:
        clients = _all_clients(session)
        if not clients:
            raise HTTPException(404, "no clients — POST /seed first")
        return run_simulation(clients, ML_MODEL)
