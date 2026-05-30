"""
HackathonRadar FastAPI Backend
Serves hackathon data, manages the 24-hour scrape scheduler,
and provides a CSV download endpoint.
"""
import csv
import io
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel as PydanticBaseModel

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core import scraper, store
from models import ScraperStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hackathon_radar")

# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=True)

class LoginRequest(PydanticBaseModel):
    password: str


def verify_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)):
    """Validate the Bearer token in the Authorization header."""
    expected = os.getenv("ACCESS_TOKEN", "")
    if not expected:
        return
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

scheduler = BackgroundScheduler(timezone="UTC")


def _scheduled_scrape():
    logger.info("Scheduler triggered 24-hour scrape cycle.")
    scraper.run_scrape_cycle()


def _initial_scrape():
    status = store.get_status()
    if status["last_run"] is None:
        logger.info("No cache found — running initial scrape in background.")
        t = threading.Thread(target=scraper.run_scrape_cycle, daemon=True)
        t.start()
    else:
        logger.info("Cache found (last run: %s) — skipping initial scrape.", status["last_run"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HackathonRadar starting up...")
    scheduler.add_job(_scheduled_scrape, trigger="interval", hours=24, id="scrape_job", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler running — interval: 24 hours")
    _initial_scrape()
    yield
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="HackathonRadar API",
    description="AI-powered hackathon discovery engine — 24h scrape cycle",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/hackathons", summary="Get active hackathons", dependencies=[Depends(verify_token)])
def get_hackathons(category: str = Query(None, description="Filter by category e.g. AI, Web3")):
    hackathons = store.get_active_hackathons(category=category)
    return {"count": len(hackathons), "hackathons": hackathons}


@app.get("/api/hackathons/export/csv", summary="Download hackathons as CSV", dependencies=[Depends(verify_token)])
def export_csv(category: str = Query(None), include_expired: bool = Query(False)):
    if include_expired:
        hackathons = store.get_all_hackathons()
    else:
        hackathons = store.get_active_hackathons(category=category)

    output = io.StringIO()
    fieldnames = ["title", "organizer", "deadline", "start_date", "prize",
                  "location", "categories", "url", "description", "source", "vetted_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for h in hackathons:
        row = dict(h)
        row["categories"] = ", ".join(h.get("categories", []))
        writer.writerow(row)

    output.seek(0)
    filename = "hackathons.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/status", summary="Get scraper status", response_model=ScraperStatus, dependencies=[Depends(verify_token)])
def get_status():
    status = store.get_status()
    return ScraperStatus(is_running=scraper.is_scraping(), scrape_interval_hours=24, **status)


@app.post("/api/refresh", summary="Manually trigger a scrape cycle", dependencies=[Depends(verify_token)])
def refresh():
    if scraper.is_scraping():
        return {"message": "Scrape already in progress", "status": "running"}
    t = threading.Thread(target=scraper.run_scrape_cycle, daemon=True)
    t.start()
    return {"message": "Scrape cycle triggered", "status": "started"}


@app.get("/api/categories", summary="Get all available categories", dependencies=[Depends(verify_token)])
def get_categories():
    hackathons = store.get_active_hackathons()
    cats: set = set()
    for h in hackathons:
        for c in h.get("categories", []):
            cats.add(c)
    return {"categories": sorted(list(cats))}


@app.post("/api/auth", summary="Authenticate with frontend password")
def login(body: LoginRequest):
    """
    Validates the 6-character alphanumeric frontend password.
    Returns the API access token on success — password is never stored client-side.
    """
    frontend_password = os.getenv("FRONTEND_PASSWORD", "")
    access_token = os.getenv("ACCESS_TOKEN", "")

    if not frontend_password:
        # Dev mode: no password set, return token directly
        return {"token": access_token}

    if body.password != frontend_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
        )

    return {"token": access_token}


@app.get("/health")
def health():
    return {"status": "ok", "service": "HackathonRadar"}
