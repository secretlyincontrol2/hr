from pydantic import BaseModel
from typing import Optional, List


class Hackathon(BaseModel):
    id: str
    title: str
    organizer: str
    description: str
    url: str
    deadline: Optional[str] = None          # ISO date string e.g. "2026-06-30"
    start_date: Optional[str] = None
    prize: Optional[str] = None
    categories: List[str] = []              # ["AI", "Web3", "Open Source", ...]
    location: str = "Remote"               # "Remote" | "In-Person: City" | "Hybrid"
    source: str = "unknown"                # "gemini" | "tavily" | "both"
    vetted_at: Optional[str] = None        # ISO timestamp of when AI vetted it
    is_active: bool = True


class ScraperStatus(BaseModel):
    is_running: bool
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    total_found: int = 0
    total_active: int = 0
    total_expired: int = 0
    scrape_interval_hours: int = 24
