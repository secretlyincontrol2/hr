import { useState, useRef, useEffect } from 'react';

const STORAGE_KEY = 'hr_token';

/**
 * PasswordGate
 *
 * Shows a full-screen password prompt. On correct entry, the backend
 * returns the API access token which is saved to sessionStorage.
 * The password itself is NEVER stored — only the server-issued token.
 *
 * Props:
 *   onUnlocked(token: string) — called once authentication succeeds
 */
export default function PasswordGate({ onUnlocked }) {
  const [chars, setChars] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);
  const inputRefs = useRef([]);

  // Auto-focus first box on mount
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  const handleChange = (index, value) => {
    // Accept only alphanumeric, single char
    const clean = value.replace(/[^a-zA-Z0-9]/g, '').slice(-1);
    const next = [...chars];
    next[index] = clean;
    setChars(next);
    setError('');

    // Auto-advance
    if (clean && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all 6 filled
    if (clean && index === 5) {
      const fullCode = [...next].join('');
      if (fullCode.length === 6) submitPassword(fullCode);
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace') {
      if (chars[index]) {
        // Clear current
        const next = [...chars];
        next[index] = '';
        setChars(next);
      } else if (index > 0) {
        // Move back
        inputRefs.current[index - 1]?.focus();
        const next = [...chars];
        next[index - 1] = '';
        setChars(next);
      }
    } else if (e.key === 'Enter') {
      const code = chars.join('');
      if (code.length === 6) submitPassword(code);
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text')
      .replace(/[^a-zA-Z0-9]/g, '')
      .slice(0, 6)
      .split('');
    const next = ['', '', '', '', '', ''];
    pasted.forEach((c, i) => { next[i] = c; });
    setChars(next);
    if (pasted.length === 6) {
      inputRefs.current[5]?.focus();
      submitPassword(next.join(''));
    } else {
      inputRefs.current[pasted.length]?.focus();
    }
  };

  const submitPassword = async (code) => {
    if (loading) return;
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: code }),
      });

      const data = await res.json();

      if (!res.ok) {
        triggerError('Incorrect password. Try again.');
        return;
      }

      // Store token in sessionStorage — NOT the password
      if (data.token) {
        sessionStorage.setItem(STORAGE_KEY, data.token);
      }
      onUnlocked(data.token || '');
    } catch {
      triggerError('Connection error. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  const triggerError = (msg) => {
    setError(msg);
    setShake(true);
    setChars(['', '', '', '', '', '']);
    setTimeout(() => {
      setShake(false);
      inputRefs.current[0]?.focus();
    }, 600);
  };

  return (
    <div className="gate-overlay">
      <div className={`gate-card${shake ? ' gate-shake' : ''}`}>
        <div className="gate-logo">
          <div className="gate-logo-icon">HR</div>
          <span className="gate-logo-text">Hackathon<span>Radar</span></span>
        </div>

        <h1 className="gate-title">Access Required</h1>
        <p className="gate-subtitle">
          Enter your 6-character access code to continue
        </p>

        <div className="gate-inputs" onPaste={handlePaste}>
          {chars.map((char, i) => (
            <input
              key={i}
              id={`gate-input-${i}`}
              ref={el => (inputRefs.current[i] = el)}
              className={`gate-cell${char ? ' gate-cell--filled' : ''}`}
              type="text"
              inputMode="text"
              maxLength={2}
              value={char}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              onChange={e => handleChange(i, e.target.value)}
              onKeyDown={e => handleKeyDown(i, e)}
              disabled={loading}
              aria-label={`Character ${i + 1} of 6`}
            />
          ))}
        </div>

        {error && <p className="gate-error" role="alert">{error}</p>}

        <button
          id="gate-submit"
          className="gate-btn"
          onClick={() => submitPassword(chars.join(''))}
          disabled={loading || chars.join('').length < 6}
        >
          {loading ? (
            <span className="gate-spinner" />
          ) : (
            'Unlock'
          )}
        </button>

        <p className="gate-hint">
          Password is validated server-side
        </p>
      </div>
    </div>
  );
}

export { STORAGE_KEY };
