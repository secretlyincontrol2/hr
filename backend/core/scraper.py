"""
Scraper Orchestrator — runs both Gemini and Tavily agents,
merges and deduplicates results, then vets them.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from agents.gemini_agent import search_hackathons_with_gemini
from agents.tavily_agent import search_hackathons_with_tavily
from core.vetter import vet_hackathons
from core import store

logger = logging.getLogger(__name__)

_is_scraping = False


def is_scraping() -> bool:
    return _is_scraping


def _generate_id(hackathon: dict) -> str:
    """Generate a stable ID from URL or title."""
    key = hackathon.get("url") or hackathon.get("title", "unknown")
    return hashlib.md5(key.encode()).hexdigest()[:12]




def _assign_ids(hackathons: List[dict]) -> List[dict]:
    for h in hackathons:
        h["id"] = _generate_id(h)
    return hackathons


def run_scrape_cycle() -> dict:
    """
    Full scrape cycle:
    1. Gemini search
    2. Tavily deep search
    3. Merge + deduplicate
    4. AI vetting
    5. Save to cache
    """
    global _is_scraping

    if _is_scraping:
        logger.warning("Scrape cycle already in progress, skipping.")
        return store.get_status()

    _is_scraping = True
    logger.info("=" * 60)
    logger.info("Starting scrape cycle at %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 60)

    try:
        def on_batch_found(batch: List[dict]):
            if not batch:
                return
            # 1. Vet first so URLs are canonicalized via Google Search
            vetted = vet_hackathons(batch)
            # 2. Assign IDs based on the exact canonical URL
            vetted_with_ids = _assign_ids(vetted)
            # 3. Save incrementally
            next_run = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            store.save_hackathons(vetted_with_ids, next_run=next_run)
            logger.info("Incrementally saved %d vetted hackathons.", len(vetted_with_ids))

        # Phase 1: Search with Gemini
        logger.info("Phase 1: Gemini Search Agent")
        search_hackathons_with_gemini(on_batch_found=on_batch_found)

        # Phase 2: Deep search with Tavily
        logger.info("Phase 2: Tavily Deep Search Agent")
        search_hackathons_with_tavily(on_batch_found=on_batch_found)

        status = store.get_status()
        logger.info("Scrape cycle complete. Status: %s", status)
        return status

    except Exception as e:
        logger.error("Scrape cycle failed: %s", e, exc_info=True)
        return store.get_status()
    finally:
        _is_scraping = False
