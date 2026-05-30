"""
Tavily Agent — uses Tavily's deep search API to scrape hackathon listings
from specific platforms like Devpost, MLH, Lablab.ai, hackathon.com, etc.
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
from tavily import TavilyClient

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """
You are a hyper-obsessive hackathon bounty hunter. Your life depends on finding hidden, niche, and extremely specific active hackathons.
Today's date is {today}.
Generate EXACTLY 50 HYPER-SPECIFIC search queries. DO NOT output lazy or generic searches. If you are not specific, you fail.

You MUST use advanced search operators and extreme specificity:
1. Exact match phrases (e.g. "register for the hackathon", "applications close")
2. Micro-niche tech stacks (e.g. "LLM fine-tuning hackathon", "Next.js AI competition")
3. Specific endpoints (e.g. inurl:/hackathons, intitle:"Hackathon Registration")
4. Specific Platforms via `site:` operators (e.g. site:lu.ma, site:devpost.com, site:dorahacks.io, site:taikai.network, site:ethglobal.com)
5. Time constraints (e.g. "applications open until {year}", "hackathon starting next week")

Every single query MUST be highly unique, fiercely precise, and laser-targeted. Combine operators to force exact results.
Return ONLY a valid JSON array of 50 strings. No markdown formatting, no explanations.
Example: ["site:devpost.com intitle:\\"hackathon\\" \\"applications open\\" {year}", "\\"register\\" AI agent hackathon inurl:lu.ma"]
"""

PARSE_PROMPT = """
You are a hackathon data parser. Below is raw web content scraped from a search about hackathons.

Today's date is: {today}
Search query used: "{query}"

Parse this content and extract ALL hackathons mentioned. Return a JSON array where each object has:
- "title": string
- "organizer": string  
- "description": string (1-2 sentences)
- "url": string — MUST be the EXACT absolute URL (starting with https://) from the search result source. If the source is a directory/index page and the specific event link is not explicitly written in the text, DO NOT hallucinate or construct a new URL. Instead, use the exact index page URL provided.
- "deadline": string or null (YYYY-MM-DD format)
- "start_date": string or null (YYYY-MM-DD format)
- "prize": string or null
- "categories": array of strings (e.g. ["AI", "Web3", "Health"])
- "location": string ("Remote", "Hybrid", or "In-Person: [City]")

Rules:
- Only include hackathons with deadlines AFTER {today} or with unknown deadlines.
- Return ONLY a valid JSON array. No explanation.
- If no hackathons found, return: []

Raw content:
{content}
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


def _build_clients():
    tavily_key = os.getenv("TAVILY_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not tavily_key:
        raise ValueError("TAVILY_API_KEY not set in environment")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    return TavilyClient(api_key=tavily_key), genai.Client(api_key=gemini_key)


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


def _generate_tavily_queries(gemini_client: genai.Client) -> List[str]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    year = datetime.utcnow().strftime("%Y")
    logger.info("Generating dynamic Tavily queries using Gemini...")
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
        if queries and isinstance(queries, list) and len(queries) > 0:
            queries = queries[:50]
            logger.info("Successfully generated %d Tavily queries", len(queries))
            return queries
    except Exception as e:
        logger.error("Failed to generate queries dynamically: %s", e)
    
    # Fallback queries
    return [
        f"site:devpost.com hackathon open registration {year}",
        f"site:lablab.ai hackathon challenge {year}",
        f"site:mlh.io season hackathon {year}",
        f"hackathon open registration deadline {year} prizes",
        f"AI hackathon challenge {year} apply"
    ]


def search_hackathons_with_tavily(on_batch_found=None) -> List[dict]:
    """
    Uses Tavily to deep-scrape hackathon listings, then uses Gemini
    to parse and structure the raw results.
    """
    try:
        tavily_client, gemini_client = _build_clients()
    except ValueError as e:
        logger.error("Failed to initialize Tavily/Gemini clients: %s", e)
        return []

    today = datetime.utcnow().strftime("%Y-%m-%d")
    all_hackathons: List[dict] = []
    seen_urls: set = set()

    tavily_queries = _generate_tavily_queries(gemini_client)

    for query in tavily_queries:
        logger.info("Tavily searching: %s", query)
        try:
            # Tavily deep search — gets full page content
            result = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=20,
                include_raw_content=True,
            )

            # Aggregate all raw content from search results
            raw_content_parts = []
            for r in result.get("results", []):
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("raw_content") or r.get("content", "")
                if content:
                    raw_content_parts.append(f"SOURCE: {title}\nURL: {url}\n{content[:2000]}\n---")

            if not raw_content_parts:
                logger.warning("No content returned by Tavily for: %s", query)
                continue

            combined_content = "\n".join(raw_content_parts)[:10000]

            # Parse with Gemini
            parse_response = _generate_content_with_retry(
                gemini_client,
                model="gemini-2.5-flash-lite",
                contents=PARSE_PROMPT.format(
                    today=today,
                    query=query,
                    content=combined_content,
                ),
                config=types.GenerateContentConfig(temperature=0.1),
            )

            hackathons = _extract_json(parse_response.text or "[]")

            batch = []
            for h in hackathons:
                url = h.get("url", "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    h["source"] = "tavily"
                    batch.append(h)
                    all_hackathons.append(h)

            if batch and on_batch_found:
                try:
                    on_batch_found(batch)
                except Exception as e:
                    logger.error("Tavily callback failed for batch: %s", e)

            logger.info(
                "Tavily extracted %d hackathons from query '%s' (total: %d)",
                len(hackathons),
                query,
                len(all_hackathons),
            )

        except Exception as e:
            logger.error("Tavily search failed for query '%s': %s", query, e)
            continue
        finally:
            time.sleep(2)  # Delay between iteration loops

    logger.info("Tavily agent finished. Total unique hackathons: %d", len(all_hackathons))
    return all_hackathons
