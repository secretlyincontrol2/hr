export default function HackathonCard({ hackathon }) {
  const {
    title, organizer, description, url, deadline,
    prize, categories = [], location, source,
  } = hackathon;

  const daysLeft = deadline ? Math.ceil(
    (new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24)
  ) : null;

  const deadlineLabel = deadline
    ? new Date(deadline).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'TBA';

  const isUrgent = daysLeft !== null && daysLeft <= 7;

  const sourceClass = `source-badge source-${source === 'both' ? 'both' : source}`;
  const sourceLabel = source === 'both' ? 'Both' : source === 'gemini' ? 'Gemini' : 'Tavily';

  return (
    <article className="card">
      <div className="card-header">
        <h2 className="card-title">{title}</h2>
        <span className={sourceClass}>{sourceLabel}</span>
      </div>

      {organizer && (
        <div className="card-organizer">
          <span>{organizer}</span>
        </div>
      )}

      {description && <p className="card-desc">{description}</p>}

      <div className="card-meta">
        <div className="meta-row">
          <span className="meta-label">Deadline</span>
          <span className={`meta-value deadline${isUrgent ? ' urgent' : ''}`}>
            {deadlineLabel}
            {daysLeft !== null && (
              <span style={{ marginLeft: '0.4rem', fontSize: '0.75rem', opacity: 0.8 }}>
                ({isUrgent ? `${daysLeft}d left!` : `${daysLeft}d left`})
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
          {categories.map(c => (
            <span key={c} className="cat-tag">{c}</span>
          ))}
        </div>
      )}

      <div className="card-footer">
        <span className="location-badge">
          {location.startsWith('In-Person') ? 'In-Person:' : location === 'Hybrid' ? 'Hybrid' : 'Remote'}
          &nbsp;{location}
        </span>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="apply-btn"
          id={`apply-${hackathon.id}`}
        >
          Apply Now ↗
        </a>
      </div>
    </article>
  );
}
