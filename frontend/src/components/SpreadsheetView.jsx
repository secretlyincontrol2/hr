import { useState, useMemo } from 'react';

const COLUMNS = [
  { key: 'title',      label: 'Hackathon',   width: '220px', sortable: true },
  { key: 'organizer',  label: 'Organizer',   width: '150px', sortable: true },
  { key: 'deadline',   label: 'Deadline',    width: '120px', sortable: true },
  { key: '_days',      label: 'Days Left',   width: '95px',  sortable: true },
  { key: 'prize',      label: 'Prize',       width: '140px', sortable: false },
  { key: 'location',   label: 'Location',    width: '130px', sortable: true },
  { key: 'categories', label: 'Categories',  width: '180px', sortable: false },
  { key: 'source',     label: 'Source',      width: '80px',  sortable: true },
  { key: '_apply',     label: 'Link',        width: '80px',  sortable: false },
];

function daysLeft(deadline) {
  if (!deadline) return null;
  return Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24));
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatUrl(url) {
  if (!url) return '#';
  if (!/^https?:\/\//i.test(url)) {
    return 'https://' + url;
  }
  return url;
}

export default function SpreadsheetView({ hackathons }) {
  const [sortKey, setSortKey] = useState('deadline');
  const [sortDir, setSortDir] = useState('asc');

  const handleSort = (key) => {
    if (!key || key === '_apply') return;
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    return [...hackathons].sort((a, b) => {
      let av, bv;
      if (sortKey === '_days') {
        av = daysLeft(a.deadline) ?? 9999;
        bv = daysLeft(b.deadline) ?? 9999;
      } else {
        av = (a[sortKey] ?? '').toString().toLowerCase();
        bv = (b[sortKey] ?? '').toString().toLowerCase();
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [hackathons, sortKey, sortDir]);

  const arrow = (key) => {
    if (sortKey !== key) return <span className="sh-arrow sh-arrow--inactive">↕</span>;
    return <span className="sh-arrow">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="sh-wrapper">
      <div className="sh-scroll">
        <table className="sh-table" role="grid">
          <thead>
            <tr className="sh-head-row">
              <th className="sh-row-num sh-th">#</th>
              {COLUMNS.map(col => (
                <th
                  key={col.key}
                  className={`sh-th${col.sortable ? ' sh-th--sortable' : ''}`}
                  style={{ minWidth: col.width }}
                  onClick={() => col.sortable && handleSort(col.key)}
                  aria-sort={sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span className="sh-th-inner">
                    {col.label}
                    {col.sortable && arrow(col.key)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((h, idx) => {
              const days = daysLeft(h.deadline);
              const urgent = days !== null && days <= 7;
              const soon   = days !== null && days <= 14 && !urgent;

              return (
                <tr key={h.id || idx} className={`sh-row${idx % 2 === 0 ? '' : ' sh-row--alt'}`}>
                  <td className="sh-row-num sh-td sh-td--num">{idx + 1}</td>

                  {/* Title */}
                  <td className="sh-td sh-td--title">
                    <span className="sh-cell-title">{h.title}</span>
                  </td>

                  {/* Organizer */}
                  <td className="sh-td sh-td--clip">{h.organizer || '—'}</td>

                  {/* Deadline */}
                  <td className="sh-td sh-td--date">{fmtDate(h.deadline)}</td>

                  {/* Days Left */}
                  <td className="sh-td sh-td--center">
                    {days === null ? (
                      <span className="sh-badge sh-badge--gray">TBA</span>
                    ) : urgent ? (
                      <span className="sh-badge sh-badge--red">{days}d</span>
                    ) : soon ? (
                      <span className="sh-badge sh-badge--yellow">{days}d</span>
                    ) : (
                      <span className="sh-badge sh-badge--green">{days}d</span>
                    )}
                  </td>

                  {/* Prize */}
                  <td className="sh-td sh-td--clip sh-td--prize">{h.prize || '—'}</td>

                  {/* Location */}
                  <td className="sh-td sh-td--clip">{h.location || 'Remote'}</td>

                  {/* Categories */}
                  <td className="sh-td">
                    <div className="sh-cats">
                      {(h.categories || []).slice(0, 3).map(c => (
                        <span key={c} className="sh-cat">{c}</span>
                      ))}
                      {h.categories?.length > 3 && (
                        <span className="sh-cat sh-cat--more">+{h.categories.length - 3}</span>
                      )}
                    </div>
                  </td>

                  {/* Source */}
                  <td className="sh-td sh-td--center">
                    <span className={`sh-source sh-source--${h.source === 'both' ? 'both' : h.source}`}>
                      {h.source === 'both' ? 'Both' : h.source === 'tavily' ? 'Tavily' : 'Gemini'}
                    </span>
                  </td>

                  {/* Apply */}
                  <td className="sh-td sh-td--center">
                    <a
                      href={formatUrl(h.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="sh-apply-btn"
                      id={`row-apply-${h.id}`}
                    >
                      Apply
                    </a>
                  </td>
                </tr>
              );
            })}

            {sorted.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length + 1} className="sh-empty">
                  No hackathons found. Try adjusting your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
