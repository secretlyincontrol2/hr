# HackathonRadar

AI-powered hackathon discovery engine. Scrapes the web every 24 hours using Gemini + Tavily, vets all deadlines, and displays only active hackathons you can apply to right now.

---

## Setup

### 1. Add API Keys

Copy the backend env example:
```
cd backend
copy .env.example .env
```

Then open `backend/.env` and fill in:
```
GEMINI_API_KEY=...     # https://aistudio.google.com/app/apikey
TAVILY_API_KEY=...     # https://app.tavily.com
```

### 2. Run the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On first start, it will immediately scrape for hackathons in the background. Subsequent scrapes run every 24 hours automatically.

### 3. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Features

- **Dual AI Scraping** — Gemini (Google Search grounding) + Tavily deep search
- **AI Vetting** — Gemini cross-checks every deadline against today's date
- **24h Auto-Scrape** — Runs non-stop via APScheduler
- **Search & Filter** — By keyword, category, and location
- **CSV Download** — Export all active hackathons as a spreadsheet
- **Urgency Alerts** — Cards highlight hackathons closing within 7 days

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/hackathons` | All active hackathons |
| GET | `/api/hackathons?category=AI` | Filter by category |
| GET | `/api/hackathons/export/csv` | Download as CSV |
| GET | `/api/status` | Scraper status & stats |
| POST | `/api/refresh` | Trigger manual scrape |
| GET | `/api/categories` | List all categories |

---

## Airtable Table Setup (Optional)

The app uses a local JSON cache by default (`hackathons_cache.json`).
