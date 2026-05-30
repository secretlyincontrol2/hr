import { useState, useEffect, useRef } from 'react';
import PasswordGate, { STORAGE_KEY } from './components/PasswordGate.jsx';
import SpreadsheetView from './components/SpreadsheetView.jsx';

const API = import.meta.env.VITE_API_URL || '/api';

function getAuthHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function formatUrl(url) {
  if (!url) return '#';
  if (!/^https?:\/\//i.test(url)) {
    return 'https://' + url;
  }
  return url;
}

export default function App() {
  // ── Auth ────────────────────────────────────
  const [token, setToken] = useState(() => sessionStorage.getItem(STORAGE_KEY) || '');
  const [authed, setAuthed] = useState(() => !!sessionStorage.getItem(STORAGE_KEY));

  const handleUnlocked = (t) => {
    setToken(t);
    setAuthed(true);
  };

  // ── Data ────────────────────────────────────
  const [hackathons, setHackathons] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);

  // ── UI state ────────────────────────────────
  const [view, setView] = useState(() => (typeof window !== 'undefined' && window.innerWidth < 768) ? 'cards' : 'sheet');
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [locFilter, setLocFilter] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef(null);

  const headers = getAuthHeaders(token);

  // ── Fetchers ────────────────────────────────
  const fetchHackathons = async (cat = '') => {
    try {
      const url = cat ? `${API}/hackathons?category=${encodeURIComponent(cat)}` : `${API}/hackathons`;
      const res = await fetch(url, { headers });
      if (res.status === 401) { setAuthed(false); return; }
      const data = await res.json();
      setHackathons(data.hackathons || []);
    } catch (e) {
      console.error('Fetch hackathons failed:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API}/status`, { headers });
      if (res.ok) setStatus(await res.json());
    } catch { /* silent */ }
  };

  const fetchCategories = async () => {
    try {
      const res = await fetch(`${API}/categories`, { headers });
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories || []);
      }
    } catch { /* silent */ }
  };

  // ── Initial load ────────────────────────────
  useEffect(() => {
    if (!authed) return;
    fetchHackathons();
    fetchStatus();
    fetchCategories();
  }, [authed]);

  // ── Poll status every 15s ───────────────────
  useEffect(() => {
    if (!authed) return;
    pollRef.current = setInterval(async () => {
      await fetchStatus();
    }, 15000);
    return () => clearInterval(pollRef.current);
  }, [authed, token]);

  // ── Client-side filter ───────────────────────
  useEffect(() => {
    let result = [...hackathons];
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(h =>
        h.title?.toLowerCase().includes(q) ||
        h.organizer?.toLowerCase().includes(q) ||
        h.description?.toLowerCase().includes(q) ||
        h.categories?.some(c => c.toLowerCase().includes(q))
      );
    }
    if (locFilter) {
      result = result.filter(h => {
        if (locFilter === 'Remote') return h.location === 'Remote';
        if (locFilter === 'In-Person') return h.location?.startsWith('In-Person');
        if (locFilter === 'Hybrid') return h.location === 'Hybrid';
        return true;
      });
    }
    setFiltered(result);
  }, [hackathons, search, locFilter]);

  // ── Category filter (server-side) ───────────
  const handleCatChange = (e) => {
    const val = e.target.value;
    setCatFilter(val);
    setLoading(true);
    fetchHackathons(val);
  };

  // ── Manual refresh ───────────────────────────
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API}/refresh`, { method: 'POST', headers });
      await fetchStatus();
    } catch { /* silent */ }
    setTimeout(() => setRefreshing(false), 2000);
  };

  // ── CSV Download ─────────────────────────────
  const handleDownload = async () => {
    const params = catFilter ? `?category=${encodeURIComponent(catFilter)}` : '';
    const res = await fetch(`${API}/hackathons/export/csv${params}`, { headers });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'hackathons.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Gate ─────────────────────────────────────
  if (!authed) return <PasswordGate onUnlocked={handleUnlocked} />;

  const isScraping = status?.is_running;

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">HR</div>
            <span className="logo-text">Hackathon<span>Radar</span></span>
          </div>

          <div className="header-right">
            {/* View Toggle */}
            <div className="view-toggle">
              <button
                id="btn-view-sheet"
                className={`view-toggle-btn${view === 'sheet' ? ' active' : ''}`}
                onClick={() => setView('sheet')}
              >
                Spreadsheet
              </button>
              <button
                id="btn-view-cards"
                className={`view-toggle-btn${view === 'cards' ? ' active' : ''}`}
                onClick={() => setView('cards')}
              >
                Cards
              </button>
            </div>

            <button
              id="btn-refresh"
              className="btn btn-ghost"
              onClick={handleRefresh}
              disabled={refreshing || isScraping}
            >
              <span className={refreshing || isScraping ? 'spin' : ''}>&#8635;</span>
              {isScraping ? 'Scraping...' : 'Refresh'}
            </button>

            <button
              id="btn-download"
              className="btn btn-download"
              onClick={handleDownload}
            >
              Download CSV
            </button>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="hero">
        <span className="hero-tag">V1.0.0 / The Editorial Update</span>
        <h1>Find Hackathons.<br />Apply Today.</h1>
        <p>
          AI-powered discovery engine scraping the web every 24 hours.
          Every listing is vetted by Gemini — no expired deadlines.
        </p>
      </section>

      {/* STATS BAR */}
      <div className="stats-bar">
        <div className="stat-chip">
          <span className={`dot${isScraping ? '' : ' idle'}`} />
          {isScraping ? 'Scraping now...' : 'Live'}
        </div>
        {status && (
          <>
            <div className="stat-chip">
              Active: <span className="value">{status.total_active}</span>
            </div>
            <div className="stat-chip">
              Filtered: <span className="value">{status.total_expired}</span>
            </div>
            {status.last_run && (
              <div className="stat-chip">
                Last scan: <strong>{new Date(status.last_run).toLocaleString()}</strong>
              </div>
            )}
            {status.next_run && (
              <div className="stat-chip">
                Next: <strong>{new Date(status.next_run).toLocaleString()}</strong>
              </div>
            )}
          </>
        )}
        <div className="spacer" />
        <div className="stat-chip">24h auto-scrape</div>
      </div>

      {/* SCRAPING BANNER */}
      {isScraping && (
        <div className="scraping-banner">
          <div className="scraping-inner">
            <span className="spin">&#8635;</span>
            AI is scanning the web for new hackathons using Gemini Search + Tavily.
            Results will appear automatically when ready.
          </div>
        </div>
      )}

      {/* FILTER BAR */}
      <div className="filter-bar">
        <div className="search-box">
          <span className="icon">S</span>
          <input
            id="search-input"
            type="text"
            placeholder="Search hackathons, categories, organizers..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <select
          id="filter-category"
          className="filter-select"
          value={catFilter}
          onChange={handleCatChange}
        >
          <option value="">All Categories</option>
          {categories.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <select
          id="filter-location"
          className="filter-select"
          value={locFilter}
          onChange={e => setLocFilter(e.target.value)}
        >
          <option value="">All Locations</option>
          <option value="Remote">Remote</option>
          <option value="In-Person">In-Person</option>
          <option value="Hybrid">Hybrid</option>
        </select>
      </div>

      {/* RESULT COUNT */}
      {!loading && (
        <div className="result-count">
          Showing <strong>{filtered.length}</strong> active hackathon{filtered.length !== 1 ? 's' : ''}
          {search && ` matching "${search}"`}
          {catFilter && ` in ${catFilter}`}
        </div>
      )}

      {/* MAIN CONTENT */}
      <main className="main">
        {loading ? (
          <LoadingSkeleton />
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">--</div>
            <h2>{hackathons.length === 0 ? 'No hackathons yet' : 'No matches found'}</h2>
            <p>
              {hackathons.length === 0
                ? 'The AI scraper is warming up. Click Refresh or wait for the next auto-scan.'
                : 'Try adjusting your filters or search term.'}
            </p>
          </div>
        ) : view === 'sheet' ? (
          <SpreadsheetView hackathons={filtered} />
        ) : (
          <div className="grid">
            {filtered.map(h => <HackathonCard key={h.id} hackathon={h} />)}
          </div>
        )}
      </main>

      {/* FOOTER */}
      <footer className="footer">
        <p>
          Powered by{' '}
          <a href="https://aistudio.google.com" target="_blank" rel="noopener noreferrer">Gemini AI</a>
          {' '}+{' '}
          <a href="https://tavily.com" target="_blank" rel="noopener noreferrer">Tavily</a>
          {' '}· Scrapes every 24 hours · All deadlines AI-verified
        </p>
      </footer>
    </div>
  );
}

// ── Skeleton ────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="loading-grid">
      {Array.from({ length: 6 }).map((_, i) => (
        <div className="skeleton" key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="sk-line w80 h20" />
            <div className="sk-line" style={{ width: 55, height: 20 }} />
          </div>
          <div className="sk-line w60" />
          <div className="sk-line" />
          <div className="sk-line w80" />
          <div className="sk-line w60" />
          <div style={{ display: 'flex', gap: 8 }}>
            <div className="sk-line" style={{ width: 60, height: 22 }} />
            <div className="sk-line" style={{ width: 48, height: 22 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Card View ───────────────────────────────────
function HackathonCard({ hackathon }) {
  const { title, organizer, description, url, deadline, prize, categories = [], location, source } = hackathon;

  const daysLeft = deadline
    ? Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24))
    : null;

  const deadlineLabel = deadline
    ? new Date(deadline).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'TBA';

  const isUrgent = daysLeft !== null && daysLeft <= 7;
  const sourceClass = `source-badge source-${source === 'both' ? 'both' : source || 'gemini'}`;
  const sourceLabel = source === 'both' ? 'Both' : source === 'tavily' ? 'Tavily' : 'Gemini';

  return (
    <article className="card">
      <div className="card-header">
        <h2 className="card-title">{title}</h2>
        <span className={sourceClass}>{sourceLabel}</span>
      </div>

      {organizer && <div className="card-organizer">{organizer}</div>}
      {description && <p className="card-desc">{description}</p>}

      <div className="card-meta">
        <div className="meta-row">
          <span className="meta-label">Deadline</span>
          <span className={`meta-value deadline${isUrgent ? ' urgent' : ''}`}>
            {deadlineLabel}
            {daysLeft !== null && (
              <span style={{ marginLeft: '0.4rem', fontSize: '0.72rem', opacity: 0.85 }}>
                {isUrgent ? ` · ${daysLeft}d left!` : ` · ${daysLeft}d left`}
              </span>
            )}
          </span>
        </div>
        {prize && (
          <div className="meta-row">
            <span className="meta-label">Prize</span>
            <span className="meta-value prize">{prize}</span>
          </div>
        )}
      </div>

      {categories.length > 0 && (
        <div className="card-cats">
          {categories.map(c => <span key={c} className="cat-tag">{c}</span>)}
        </div>
      )}

      <div className="card-footer">
        <span className="location-badge">
          {location?.startsWith('In-Person') ? 'In-Person' : location === 'Hybrid' ? 'Hybrid' : 'Remote'}
        </span>
        <a href={formatUrl(url)} target="_blank" rel="noopener noreferrer"
           className="apply-btn" id={`apply-${hackathon.id}`}>
          Apply Now
        </a>
      </div>
    </article>
  );
}
