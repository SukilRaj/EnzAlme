/**
 * Horizontal tick-mark meter for a single compatibility factor
 * (pollutant / pH / temperature / salinity). Styled as an instrument
 * scale rather than a rounded SaaS progress pill.
 */
export default function CompatMeter({ label, value, status, note }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const ticks = Array.from({ length: 10 }, (_, i) => i);
  const color = pct >= 70 ? "var(--moss)" : pct >= 40 ? "var(--amber-deep)" : "var(--clay)";

  return (
    <div className="compat-meter">
      <div className="compat-meter-head">
        <span className="compat-meter-label">{label}</span>
        <span className="compat-meter-value mono" style={{ color }}>
          {pct}%{status === "unknown" && <span className="compat-meter-unknown"> · unknown</span>}
        </span>
      </div>
      <div className="compat-meter-track">
        {ticks.map((i) => (
          <span
            key={i}
            className="compat-meter-tick"
            style={{ background: i < pct / 10 ? color : "var(--line)" }}
          />
        ))}
      </div>
      {note && <p className="compat-meter-note">{note}</p>}
    </div>
  );
}
