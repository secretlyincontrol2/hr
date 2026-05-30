import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.gemini_agent import _perform_search

print("Testing _perform_search with 'ethereum hackathon 2026'...")
results = _perform_search("ethereum hackathon 2026")

for i, r in enumerate(results[:3]):
    print(f"[{i+1}] {r['title']}")
    print(f"    URL: {r['url']}")

if not results:
    print("NO RESULTS FOUND.")
