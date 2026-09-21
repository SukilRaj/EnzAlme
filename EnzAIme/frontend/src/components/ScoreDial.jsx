/**
 * Radial "instrument gauge" score indicator — deliberately not a generic
 * rounded progress pill. Reads like a lab meter: a partial ring with a
 * tick at the current value and the percentage set in mono type at center.
 */
export default function ScoreDial({ percent, size = 108, label }) {
  const clamped = Math.max(0, Math.min(100, percent));
  const stroke = 8;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const startAngle = -125; // degrees
  const sweep = 250; // total arc sweep in degrees
  const filledDeg = (clamped / 100) * sweep;

  const arcPath = (fromDeg, toDeg) => {
    const toRad = (d) => ((d - 90) * Math.PI) / 180;
    const x1 = cx + r * Math.cos(toRad(fromDeg));
    const y1 = cy + r * Math.sin(toRad(fromDeg));
    const x2 = cx + r * Math.cos(toRad(toDeg));
    const y2 = cy + r * Math.sin(toRad(toDeg));
    const largeArc = toDeg - fromDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  const color = clamped >= 70 ? "var(--moss)" : clamped >= 40 ? "var(--amber-deep)" : "var(--clay)";

  return (
    <div className="score-dial" style={{ width: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <path d={arcPath(startAngle, startAngle + sweep)} fill="none" stroke="var(--line)" strokeWidth={stroke} strokeLinecap="round" />
        <path
          d={arcPath(startAngle, startAngle + filledDeg)}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.4s ease" }}
        />
        <text x={cx} y={cy - 2} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={size * 0.22} fontWeight="600" fill="var(--ink-teal)">
          {Math.round(clamped)}
        </text>
        <text x={cx} y={cy + size * 0.16} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={size * 0.1} fill="var(--slate-2)">
          %
        </text>
      </svg>
      {label && <div className="score-dial-label">{label}</div>}
    </div>
  );
}
