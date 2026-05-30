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
import requests
import requests
from google import genai
from google.genai import types
from tavily import TavilyClient

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """
You are a hyper-obsessive hackathon bounty hunter. Your life depends on finding hidden, niche, and extremely specific active hackathons.
Today's date is {today}.
Generate EXACTLY 50 HYPER-SPECIFIC search queries. DO NOT output lazy or generic searches like "AI hackathons {year}". If you are not specific, you fail.

You MUST use advanced Google Search operators and extreme specificity:
1. Specific Platforms via `site:` operators (e.g. site:lu.ma, site:devpost.com, site:dorahacks.io, site:taikai.network, site:ethglobal.com)
2. Specific endpoints (e.g. inurl:/hackathons, intitle:"Hackathon Registration")
3. Micro-niche tech stacks (e.g. "zk-SNARKs hackathon", "Rust game dev hackathon", "Solana DeFi bounty")
4. Geographic Targeting: You MUST dedicate at least 15 of your 50 queries to explicitly search for hackathons in specific countries and continents. Explicitly include "Nigeria", "Africa", "UK", "US", "Singapore", "India" in the search terms (e.g. "hackathon happening in Nigeria", "in-person hackathon Lagos", "tech bounty Africa", "hackathon London UK"). The remaining queries should target "Remote" or "Global" events.
5. Time constraints (e.g. "applications open until {year}", "hackathon starting next week")

Every single query MUST be highly unique, fiercely precise, and laser-targeted. Combine operators to force exact results.
Return ONLY a valid JSON array of 50 strings. No markdown formatting, no explanations.
"""

URL_SELECTION_PROMPT = """
You are a master URL filter. I have performed a search for "{query}" and obtained the following snippets.
Your goal is to identify the most promising URLs that point DIRECTLY to specific hackathons (e.g. registration pages, devpost links, dorahacks event links).
Ignore generic directory pages (like simply "mlh.io" or "dorahacks.io/hackathons") UNLESS they are the only option. 
Ignore news articles or blogs if they don't look like registration portals.

Return ONLY a valid JSON array of strings containing the top {limit} most promising absolute URLs from these results.
Do not output markdown, do not invent URLs that are not in the JSON. If there are no good URLs, return [].

Search snippets:
{snippets}
"""

EXTRACTION_PROMPT = """
You are a hackathon data extractor. I have fetched the FULL webpage content for the following URL: {url}

Today's date is: {today}

Read the webpage content below carefully and extract the hackathon details.
Return a JSON array with exactly ONE object (if the page describes a valid hackathon), or an EMPTY array [] if the page is irrelevant/junk.

The object must have these exact fields:
- "title": string — name of the hackathon
- "organizer": string — who's hosting it
- "description": string — 2-3 sentence detailed description
- "url": string — use exactly {url}
- "deadline": string or null — application deadline in format YYYY-MM-DD (null if not found)
- "start_date": string or null — when the hackathon starts, in YYYY-MM-DD format (null if not found)
- "prize": string or null — prize info (e.g. "$10,000 total prizes", null if not found)
- "categories": array of strings — tags like ["AI", "Web3", "Open Source", "Health", "Climate", "General"]
- "location": string — "Remote", "Hybrid", or "In-Person: [City]"

IMPORTANT RULES:
1. Extract ALL fields you can find since you have the full page text. Do not leave prize or dates null if they are mentioned.
2. Only include the hackathon if its deadline is AFTER {today} OR where the deadline is unknown/not yet set.
3. Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array.

Full Webpage Markdown Content:
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
        
        # Prepend 3 explicit Nigerian queries to run first
        nigerian_queries = [
            f"hackathons in nigeria {year} apply now",
            f"lagos tech hackathon open registration {year}",
            f"nigerian tech bounty competition in-person {year}"
        ]
        
        if queries and isinstance(queries, list) and len(queries) > 0:
            queries = nigerian_queries + queries[:47]
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


def _fetch_jina_markdown(url: str) -> str:
    """Fetches the full markdown content of a page using Jina Reader API."""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        res = requests.get(jina_url, timeout=20)
        if res.ok:
            return res.text
    except Exception as e:
        logger.warning("Failed to fetch markdown for %s: %s", url, e)
    return ""

def _perform_search(query: str) -> List[dict]:
    """
    Dual-redundant search waterfall:
    1. SerpAPI (Primary - Exact Google Links)
    2. Tavily (Fallback)
    Returns standard format: [{"title": "...", "url": "...", "snippet": "..."}]
    """
    normalized_results = []
    
    # 1. SerpAPI
    serp_key = os.getenv("SERPAPI_API_KEY")
    if serp_key:
        try:
            res = requests.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": serp_key, "engine": "google", "num": 15},
                timeout=15
            )
            if res.ok:
                data = res.json()
                if "organic_results" in data:
                    logger.info("Search fulfilled by SerpAPI.")
                    for r in data["organic_results"]:
                        normalized_results.append({
                            "title": r.get("title", ""),
                            "url": r.get("link", ""),
                            "snippet": r.get("snippet", "")
                        })
                    return normalized_results
        except Exception as e:
            logger.warning("SerpAPI failed: %s. Falling back to Tavily.", e)
    else:
        logger.info("No SERPAPI_API_KEY found, falling back to Tavily.")

    # 2. Tavily
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            client = TavilyClient(api_key=tavily_key)
            data = client.search(query, search_depth="basic", max_results=15)
            if "results" in data:
                logger.info("Search fulfilled by Tavily.")
                for r in data["results"]:
                    normalized_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", "")
                    })
                return normalized_results
        except Exception as e:
            logger.warning("Tavily failed: %s. Waterfall exhausted.", e)

    return []


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
            # Step 1: Execute triple-redundant search waterfall
            search_results = _perform_search(query)
            
            if not search_results:
                logger.warning("Empty search response for query: %s", query)
                continue

            # Step 2: Ask Gemini to select the top 3 most promising URLs
            snippets_context = json.dumps(search_results, indent=2)
            selection_response = _generate_content_with_retry(
                client,
                model="gemini-2.5-flash-lite",
                contents=URL_SELECTION_PROMPT.format(
                    query=query,
                    limit=3,
                    snippets=snippets_context[:8000],
                ),
                config=types.GenerateContentConfig(temperature=0.1),
            )
            
            top_urls = _extract_json(selection_response.text or "[]")
            
            # Step 3: For each top URL, perform Deep Jina Extraction
            batch = []
            for url in top_urls:
                if not isinstance(url, str) or not url.startswith("http"):
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                logger.info("Deep extracting URL: %s", url)
                markdown_content = _fetch_jina_markdown(url)
                if not markdown_content:
                    continue
                
                # Step 4: Ask Gemini to extract full details from the Jina Markdown
                extraction_response = _generate_content_with_retry(
                    client,
                    model="gemini-2.5-flash-lite",
                    contents=EXTRACTION_PROMPT.format(
                        url=url,
                        today=today,
                        context=markdown_content[:25000],  # Give Gemini enough context but stay under limits
                    ),
                    config=types.GenerateContentConfig(temperature=0.1),
                )
                
                hackathons = _extract_json(extraction_response.text or "[]")
                
                for h in hackathons:
                    h["source"] = "gemini"
                    batch.append(h)
                    all_hackathons.append(h)
                
                time.sleep(1) # Small delay to avoid Jina rate limits
                
            if batch and on_batch_found:
                try:
                    on_batch_found(batch)
                except Exception as e:
                    logger.error("Gemini callback failed for batch: %s", e)

            logger.info("Query '%s' yielded %d hackathons (total so far: %d)", query, len(batch), len(all_hackathons))

        except Exception as e:
            logger.error("Gemini search failed for query '%s': %s", query, e)
            continue
        finally:
            time.sleep(2)  # Delay between iteration loops

    logger.info("Gemini agent finished. Total unique hackathons: %d", len(all_hackathons))
    return all_hackathons
