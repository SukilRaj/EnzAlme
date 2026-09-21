import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { LoadingState, ErrorState } from "../components/StatePanels";
import "./Mutations.css";

export default function Mutations() {
  const { enzymeId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    api
      .mutations({ enzyme_id: enzymeId, top_n: 20 })
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to analyze mutations."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [enzymeId]);

  if (loading) return <div className="container"><LoadingState message="Generating and scoring mutation candidates…" /></div>;
  if (error) return <div className="container" style={{ padding: "56px 28px" }}><ErrorState message={error} onRetry={load} /></div>;
  if (!data) return null;

  return (
    <div className="container mutations-page">
      <p className="eyebrow">Mutation prioritization</p>
      <h1>{data.enzyme_name}</h1>
      <p className="mutations-meta mono">
        {data.sequence_length} aa · {data.n_candidates_generated} candidates generated · provider: {data.provider}
      </p>

      <div className="disclaimer-panel">
        <strong>Computational prediction — experimental validation required.</strong> Structural/docking
        validation is future work and is not part of this MVP. Scores are derived from documented
        physicochemical amino-acid properties, not measured ΔΔG or fitness values.
      </div>

      <table className="mutations-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Mutation</th>
            <th>Position</th>
            <th>Original</th>
            <th>New</th>
            <th>Stability</th>
            <th>Fitness proxy</th>
            <th>Mutation score</th>
          </tr>
        </thead>
        <tbody>
          {data.mutations.map((m) => (
            <tr key={m.mutation} className={m.rank === 1 ? "top-row" : ""}>
              <td className="mono">{m.rank}</td>
              <td className="mono mutation-cell">{m.mutation}</td>
              <td className="mono">{m.position}</td>
              <td className="mono">{m.original_residue}</td>
              <td className="mono">{m.new_residue}</td>
              <td className="mono">{m.predicted_stability_score.toFixed(3)}</td>
              <td className="mono">{m.predicted_fitness_proxy.toFixed(3)}</td>
              <td className="mono score-cell">{m.mutation_score.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="future-work-card card">
        <p className="eyebrow">Future work</p>
        <h3>Structural / docking validation</h3>
        <p>
          This MVP does not perform structural modeling or docking simulations. Ranked mutation
          candidates above are a starting point for further computational (e.g. structural
          modeling, molecular dynamics) or wet-lab validation — not a final answer.
        </p>
      </div>

      <Link to={`/enzyme/${enzymeId}`} className="btn btn-ghost" style={{ marginTop: 28 }}>
        ← Back to enzyme record
      </Link>
    </div>
  );
}
