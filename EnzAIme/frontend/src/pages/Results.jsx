import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import ScoreDial from "../components/ScoreDial";
import CompatMeter from "../components/CompatMeter";
import ModeBadge from "../components/ModeBadge";
import "./Results.css";

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const result = location.state?.result;

  if (!result) {
    return (
      <div className="container results-empty">
        <h1>No results to show</h1>
        <p>Run a recommendation first to see ranked enzymes here.</p>
        <Link to="/recommend" className="btn btn-accent">Go to Recommend</Link>
      </div>
    );
  }

  const { query, recommendations, scoring_mode, disclaimer, n_candidates_evaluated, n_candidates_with_pollutant_evidence } = result;

  return (
    <div className="container results-page">
      <div className="results-head">
        <div>
          <p className="eyebrow">Step 2 of 2</p>
          <h1>Top recommended enzymes</h1>
          <p className="results-query mono">
            {query.pollutant} · pH {query.ph} · {query.temperature}°C · {query.salinity}% salinity
          </p>
        </div>
        <ModeBadge scoringMode={scoring_mode} />
      </div>

      <p className="results-summary">
        Evaluated {n_candidates_evaluated} of {n_candidates_with_pollutant_evidence} candidates with
        documented {query.pollutant} evidence. {disclaimer}
      </p>

      {recommendations.length === 0 ? (
        <div className="error-panel">
          <h3>No enzymes met the minimum pollutant compatibility threshold</h3>
          <p>Try a different pollutant, or widen the environmental parameters.</p>
        </div>
      ) : (
        <div className="results-list">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.enzyme_id} rec={rec} navigate={navigate} />
          ))}
        </div>
      )}

      <div className="results-actions">
        <Link to="/recommend" className="btn btn-ghost">Run another scenario</Link>
      </div>
    </div>
  );
}

function RecommendationCard({ rec, navigate }) {
  const [showWhy, setShowWhy] = useState(false);
  const ex = rec.explanation;

  return (
    <article className="card rec-card">
      <div className="rec-card-main">
        <div className="rec-rank mono">#{rec.rank}</div>
        <ScoreDial percent={rec.score_percent} />
        <div className="rec-info">
          <h3>{rec.enzyme_name}</h3>
          <p className="rec-meta mono">
            {rec.accession && rec.accession !== "nan" ? rec.accession : "accession pending"} · {rec.pollutant} ·
            {" "}{rec.evidence} evidence
          </p>
          <div className="rec-meters">
            <CompatMeter label="Pollutant match" value={rec.breakdown.pollutant} />
            <CompatMeter label="pH compatibility" value={rec.breakdown.ph} />
            <CompatMeter label="Temperature compatibility" value={rec.breakdown.temperature} />
            <CompatMeter
              label="Salinity compatibility"
              value={rec.breakdown.salinity}
              status={rec.salinity_status}
            />
          </div>
        </div>
      </div>

      <div className="rec-card-footer">
        <button className="btn btn-ghost" onClick={() => setShowWhy((s) => !s)}>
          {showWhy ? "Hide explanation" : "Why this enzyme?"}
        </button>
        <button className="btn btn-primary" onClick={() => navigate(`/enzyme/${rec.enzyme_id}`)}>
          View details
        </button>
      </div>

      {showWhy && (
        <div className="why-panel">
          <WhyRow label="Pollutant" text={`${ex.pollutant.input} — ${ex.pollutant.note}`} />
          <WhyRow label="pH" text={`Input ${ex.ph.input}. Reported range: ${ex.ph.reported_range}.`} />
          <WhyRow label="Temperature" text={`Input ${ex.temperature.input}°C. Reported range: ${ex.temperature.reported_range}.`} />
          <WhyRow label="Salinity" text={ex.salinity.note} />
        </div>
      )}
    </article>
  );
}

function WhyRow({ label, text }) {
  return (
    <div className="why-row">
      <span className="why-label mono">{label}</span>
      <span className="why-text">{text}</span>
    </div>
  );
}
