"""
Gemini Agent — uses Gemini 2.0 Flash with Google Search grounding
to discover and extract structured hackathon data from the web.
"""
import json
import logging
import os
import re
from datetime import datetime
from typing import List

import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """
You are a hyper-obsessive hackathon bounty hunter. Your life depends on finding hidden, niche, and extremely specific active hackathons.
Today's date is {today}.
Generate EXACTLY 50 HYPER-SPECIFIC search queries. DO NOT output lazy or generic searches like "AI hackathons {year}". If you are not specific, you fail.

You MUST use advanced Google Search operators and extreme specificity:
1. Specific Platforms via `site:` operators (e.g. site:lu.ma, site:devpost.com, site:dorahacks.io, site:taikai.network, site:ethglobal.com)
2. Specific endpoints (e.g. inurl:/hackathons, intitle:"Hackathon Registration")
3. Micro-niche tech stacks (e.g. "zk-SNARKs hackathon", "Rust game dev hackathon", "Solana DeFi bounty")
4. Exact cities or obscure locations (e.g. "hackathon happening in Austin, TX", "in-person hackathon Berlin")
5. Time constraints (e.g. "applications open until {year}", "hackathon starting next week")

Every single query MUST be highly unique, fiercely precise, and laser-targeted. Combine operators to force exact results.
Return ONLY a valid JSON array of 50 strings. No markdown formatting, no explanations.
"""

EXTRACTION_PROMPT = """
You are a hackathon data extractor. I have performed a Google Search for "{query}" and the results are shown below.

Today's date is: {today}

From the search results, extract ALL hackathons you can find. For each hackathon, return a JSON array with objects having these exact fields:
- "title": string — name of the hackathon
- "organizer": string — who's hosting it
- "description": string — 1-2 sentence description
- "url": string — MUST be the EXACT absolute URL (starting with https://) from the search result source. If the source is a directory/index page and the specific event link is not explicitly written in the text, DO NOT hallucinate or construct a new URL. Instead, use the exact index page URL provided.
- "deadline": string or null — application deadline in format YYYY-MM-DD (null if not found)
- "start_date": string or null — when the hackathon starts, in YYYY-MM-DD format (null if not found)
- "prize": string or null — prize info (e.g. "$10,000 total prizes", null if not found)
- "categories": array of strings — tags like ["AI", "Web3", "Open Source", "Health", "Climate", "General"]
- "location": string — "Remote", "Hybrid", or "In-Person: [City]"

IMPORTANT RULES:
1. Only include hackathons whose deadline is AFTER {today} OR where the deadline is unknown/not yet set.
2. Do NOT include hackathons that have already ended.
3. If you're unsure about a deadline, include it with deadline=null (we'll vet it separately).
4. Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array.
5. If no hackathons found, return an empty array: []

Search results context:
{context}
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
        raise ValueError("GEMINI_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> list:
    """Robustly extract JSON array from model response."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array inside markdown code block
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON array in the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract JSON from Gemini response: %s", text[:500])
    return []


def _generate_gemini_queries(gemini_client: genai.Client) -> List[str]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    year = datetime.utcnow().strftime("%Y")
    logger.info("Generating 150 dynamic Gemini queries...")
    try:
        response = _generate_content_with_retry(
            gemini_client,
            model="gemini-2.5-flash-lite",
            contents=QUERY_GENERATION_PROMPT.format(today=today, year=year),
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(url_context=types.UrlContext()),
                    types.Tool(googleSearch=types.GoogleSearch())
                ],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=0.7,
            ),
        )
        queries = _extract_json(response.text or "[]")
        queries = queries[:50]  # Ensure exact limit
        if queries and isinstance(queries, list) and len(queries) > 0:
            logger.info("Successfully generated %d Gemini queries", len(queries))
            return queries
    except Exception as e:
        logger.error("Failed to generate Gemini queries dynamically: %s", e)
    
    # Fallback to a few default queries
    return [
        f"active hackathons with open registration {year} apply now",
        f"hackathon open applications deadline {year} devpost",
        f"AI machine learning hackathon {year} prize money open",
        f"web3 blockchain hackathon {year} open registration",
        f"global online hackathon competition {year} prizes",
    ]


def search_hackathons_with_gemini(on_batch_found=None) -> List[dict]:
    """
    Uses Gemini 2.0 Flash with Google Search grounding to find hackathons.
    Returns a list of raw hackathon dicts.
    """
    client = _build_client()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    all_hackathons: List[dict] = []
    seen_urls: set = set()

    gemini_queries = _generate_gemini_queries(client)

    for query in gemini_queries:
        logger.info("Gemini searching: %s", query)
        try:
            # Step 1: Use Google Search grounding to get fresh web results
            search_response = _generate_content_with_retry(
                client,
                model="gemini-2.5-flash-lite",
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(url_context=types.UrlContext()),
                        types.Tool(googleSearch=types.GoogleSearch())
                    ],
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.1,
                ),
            )

            context = search_response.text or ""

            if not context:
                logger.warning("Empty search response for query: %s", query)
                continue

            # Step 2: Ask Gemini to extract structured hackathon data from the context
            extraction_response = _generate_content_with_retry(
                client,
                model="gemini-2.5-flash-lite",
                contents=EXTRACTION_PROMPT.format(
                    query=query,
                    today=today,
                    context=context[:8000],  # Limit context size
                ),
                config=types.GenerateContentConfig(
                    temperature=0.1,
                ),
            )

            hackathons = _extract_json(extraction_response.text or "[]")

            batch = []
            for h in hackathons:
                url = h.get("url", "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    h["source"] = "gemini"
                    batch.append(h)
                    all_hackathons.append(h)

            if batch and on_batch_found:
                try:
                    on_batch_found(batch)
                except Exception as e:
                    logger.error("Gemini callback failed for batch: %s", e)

            if hackathons:
                logger.info(
                    "Query '%s' yielded %d hackathons (total so far: %d)",
                    query,
                    len(hackathons),
                    len(all_hackathons),
                )

        except Exception as e:
            logger.error("Gemini search failed for query '%s': %s", query, e)
            continue
        finally:
            time.sleep(2)  # Delay between iteration loops

    logger.info("Gemini agent finished. Total unique hackathons: %d", len(all_hackathons))
    return all_hackathons
