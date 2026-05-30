export default function LoadingPulse() {
  return (
    <div className="loading-grid">
      {Array.from({ length: 6 }).map((_, i) => (
        <div className="skeleton" key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="sk-line w80 h20" />
            <div className="sk-line w40" style={{ height: 20, width: 60 }} />
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
