/**
 * Always-visible indicator of which scoring engine produced the results
 * (Section 36 — the active mode is never hidden from the user).
 */
export default function ModeBadge({ scoringMode }) {
  const isAi = scoringMode === "ai_model";
  return (
    <span className={`badge ${isAi ? "mode-badge-ai" : "mode-badge-demo"}`}>
      <span className="badge-dot" />
      {isAi ? "AI Model" : "Demo / Compatibility Engine"}
    </span>
  );
}
