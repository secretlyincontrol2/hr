"""
AI Vetting Engine — uses Gemini to cross-check all scraped hackathons
against today's date and filter out expired or invalid listings.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List

import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VETTING_PROMPT = """
You are a hackathon validator. Today's date is {today}.

Below is a JSON array of hackathons scraped from the web. Your job is to vet each one and return a cleaned, filtered list.

For each hackathon:
1. Check if the deadline has already PASSED (is before {today}). If so, set "is_active": false.
2. If the deadline is null or uncertain, check if the hackathon description/title suggests it's past (e.g., says "2025", "ended", "closed"). If clearly past, set is_active: false.
3. If the deadline appears to be in the future or is unknown, set "is_active": true.
4. IMPORTANT: URL Canonicalization. If "url" points to a generic directory/aggregator (e.g. dorahacks.io/hackathon, mlh.io, devpost.com, taikai.network) OR is missing, you MUST use your Google Search tool to search for the EXACT hackathon title and find its specific canonical URL. Update the "url" field to point directly to the event's actual registration page.
5. Normalize the "deadline" field to YYYY-MM-DD format if you can parse it, otherwise keep null.
6. Normalize "start_date" similarly.
7. Ensure "categories" is a non-empty array of tags. Add sensible defaults if missing (e.g., ["General"]).
8. Ensure "location" is one of: "Remote", "Hybrid", or starts with "In-Person:".
9. Add a "vetted_at" field with value "{timestamp}".
10. Return ONLY the JSON array of all hackathons (both active and inactive), with all fields set correctly.

Raw hackathons input:
{hackathons_json}

Return ONLY valid JSON array. No markdown fences, no explanation.
"""

def _generate_content_with_retry(client, **kwargs):
    for attempt in range(5):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str:
                logger.warning("Gemini API rate limited/503. Retrying in 10s... (Attempt %d/5)", attempt + 1)
                time.sleep(10)
            else:
                raise
    raise Exception("Max retries exceeded for Gemini API.")

def _build_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> list:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return []


def vet_hackathons(raw_hackathons: List[dict]) -> List[dict]:
    """
    Send batches of hackathons to Gemini for deadline vetting.
    Returns vetted list with is_active flags correctly set.
    """
    if not raw_hackathons:
        return []

    client = _build_client()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat()

    BATCH_SIZE = 20  # Vet 20 at a time to stay within token limits
    vetted: List[dict] = []

    for i in range(0, len(raw_hackathons), BATCH_SIZE):
        batch = raw_hackathons[i : i + BATCH_SIZE]
        logger.info(
            "Vetting batch %d-%d of %d hackathons",
            i + 1,
            i + len(batch),
            len(raw_hackathons),
        )

        try:
            response = _generate_content_with_retry(
                client,
                model="gemini-2.5-flash-lite",
                contents=VETTING_PROMPT.format(
                    today=today,
                    timestamp=timestamp,
                    hackathons_json=json.dumps(batch, indent=2),
                ),
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    tools=[types.Tool(googleSearch=types.GoogleSearch())],
                ),
            )

            batch_vetted = _extract_json(response.text or "[]")

            if batch_vetted:
                vetted.extend(batch_vetted)
            else:
                # Fallback: mark all as active with timestamp if parsing failed
                logger.warning("Vetting parse failed for batch %d, using fallback", i)
                for h in batch:
                    h["vetted_at"] = timestamp
                    if "is_active" not in h:
                        h["is_active"] = True
                vetted.extend(batch)

        except Exception as e:
            logger.error("Vetting batch %d failed: %s", i, e)
            for h in batch:
                h["vetted_at"] = timestamp
                if "is_active" not in h:
                    h["is_active"] = True
            vetted.extend(batch)
        finally:
            time.sleep(2)  # Delay between batch loops

    active = sum(1 for h in vetted if h.get("is_active", True))
    logger.info(
        "Vetting complete: %d total, %d active, %d expired",
        len(vetted),
        active,
        len(vetted) - active,
    )
    return vetted
