"""
PostgreSQL store — persists hackathon data to a Neon Postgres database.
Thread-safe. Supports filtering, UPSERTs, and CSV export.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger(__name__)

_lock = threading.Lock()

def _get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set in environment. Check .env file.")
        raise ValueError("DATABASE_URL not set")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def _init_db():
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                # Create hackathons table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hackathons (
                        id VARCHAR(255) PRIMARY KEY,
                        title VARCHAR(255),
                        organizer VARCHAR(255),
                        description TEXT,
                        url VARCHAR(1024),
                        deadline VARCHAR(255),
                        start_date VARCHAR(255),
                        prize VARCHAR(255),
                        categories JSONB,
                        location VARCHAR(255),
                        source VARCHAR(50),
                        vetted_at VARCHAR(255),
                        is_active BOOLEAN
                    );
                """)
                # Create scraper_status table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS scraper_status (
                        id INT PRIMARY KEY DEFAULT 1,
                        last_run VARCHAR(255),
                        next_run VARCHAR(255),
                        total_found INT,
                        total_active INT,
                        total_expired INT
                    );
                """)
            conn.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)

# Initialize on module import
_init_db()

def get_all_hackathons() -> List[dict]:
    with _lock:
        try:
            with _get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM hackathons;")
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Failed to get all hackathons: %s", e)
            return []

def get_active_hackathons(category: Optional[str] = None) -> List[dict]:
    hackathons = get_all_hackathons()
    active = [h for h in hackathons if h.get("is_active", True)]

    if category:
        cat_lower = category.lower()
        active = [
            h for h in active
            if any(cat_lower in c.lower() for c in h.get("categories", []))
        ]

    def sort_key(h):
        d = h.get("deadline")
        return (0, d) if d else (1, h.get("title", "").lower())

    active.sort(key=sort_key)
    return active

def get_status() -> dict:
    with _lock:
        try:
            with _get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM scraper_status WHERE id = 1;")
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            logger.error("Failed to get status: %s", e)
            
        return {
            "last_run": None,
            "next_run": None,
            "total_found": 0,
            "total_active": 0,
            "total_expired": 0,
        }

def save_hackathons(hackathons: List[dict], next_run: Optional[str] = None) -> None:
    with _lock:
        active_count = sum(1 for h in hackathons if h.get("is_active", True))
        expired_count = len(hackathons) - active_count
        
        try:
            with _get_db_connection() as conn:
                with conn.cursor() as cur:
                    # UPSERT hackathons
                    for h in hackathons:
                        cur.execute("""
                            INSERT INTO hackathons (id, title, organizer, description, url, deadline, start_date, prize, categories, location, source, vetted_at, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                title = EXCLUDED.title,
                                organizer = COALESCE(EXCLUDED.organizer, hackathons.organizer),
                                description = COALESCE(EXCLUDED.description, hackathons.description),
                                url = EXCLUDED.url,
                                deadline = COALESCE(EXCLUDED.deadline, hackathons.deadline),
                                start_date = COALESCE(EXCLUDED.start_date, hackathons.start_date),
                                prize = COALESCE(EXCLUDED.prize, hackathons.prize),
                                categories = EXCLUDED.categories,
                                location = COALESCE(EXCLUDED.location, hackathons.location),
                                source = CASE 
                                    WHEN hackathons.source != EXCLUDED.source THEN 'both' 
                                    ELSE EXCLUDED.source 
                                END,
                                vetted_at = EXCLUDED.vetted_at,
                                is_active = EXCLUDED.is_active;
                        """, (
                            h.get("id"),
                            h.get("title"),
                            h.get("organizer"),
                            h.get("description"),
                            h.get("url"),
                            h.get("deadline"),
                            h.get("start_date"),
                            h.get("prize"),
                            Json(h.get("categories", [])),
                            h.get("location"),
                            h.get("source"),
                            h.get("vetted_at"),
                            h.get("is_active")
                        ))

                    # Calculate total stats from DB after upsert
                    cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active FROM hackathons;")
                    stats_row = cur.fetchone()
                    total_db_found = stats_row['total'] if stats_row and stats_row['total'] else 0
                    total_db_active = stats_row['active'] if stats_row and stats_row['active'] else 0
                    total_db_expired = total_db_found - total_db_active

                    # UPSERT scraper_status
                    last_run = datetime.now(timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO scraper_status (id, last_run, next_run, total_found, total_active, total_expired)
                        VALUES (1, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            last_run = EXCLUDED.last_run,
                            next_run = EXCLUDED.next_run,
                            total_found = EXCLUDED.total_found,
                            total_active = EXCLUDED.total_active,
                            total_expired = EXCLUDED.total_expired;
                    """, (
                        last_run,
                        next_run,
                        total_db_found,
                        total_db_active,
                        total_db_expired
                    ))
                conn.commit()
                logger.info("Saved %d hackathons (DB now has %d total).", len(hackathons), total_db_found)
        except Exception as e:
            logger.error("Failed to save hackathons to DB: %s", e)
