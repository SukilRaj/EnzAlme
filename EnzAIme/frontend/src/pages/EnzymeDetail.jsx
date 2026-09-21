import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import SequenceBlock from "../components/SequenceBlock";
import { LoadingState, ErrorState } from "../components/StatePanels";
import "./EnzymeDetail.css";

export default function EnzymeDetail() {
  const { enzymeId } = useParams();
  const navigate = useNavigate();
  const [enzyme, setEnzyme] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    api
      .getEnzyme(enzymeId)
      .then(setEnzyme)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load enzyme."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [enzymeId]);

  if (loading) return <div className="container"><LoadingState message="Loading enzyme record…" /></div>;
  if (error) return <div className="container" style={{ padding: "56px 28px" }}><ErrorState message={error} onRetry={load} /></div>;
  if (!enzyme) return null;

  return (
    <div className="container detail-page">
      <p className="eyebrow">Enzyme record</p>
      <div className="detail-head">
        <h1>{enzyme.enzyme_name}</h1>
        {enzyme.demo_assumption && (
          <span className="badge mode-badge-demo">
            <span className="badge-dot" /> Contains demo-assumption values
          </span>
        )}
      </div>

      <div className="detail-grid">
        <div className="card detail-meta">
          <MetaRow label="Enzyme ID" value={enzyme.enzyme_id} mono />
          <MetaRow label="Accession" value={enzyme.accession} mono />
          <MetaRow label="EC number" value={enzyme.ec_number} mono />
          <MetaRow label="Pollutant" value={enzyme.pollutant} />
          <MetaRow label="Evidence type" value={enzyme.evidence_type} />
          <MetaRow label="Sequence length" value={enzyme.seq_length ? `${enzyme.seq_length} aa` : "unknown"} />
          <MetaRow label="Source" value={enzyme.source} />
          <hr className="rule" style={{ margin: "16px 0" }} />
          <MetaRow label="pH optimum" value={fmt(enzyme.pH_opt)} />
          <MetaRow label="pH range" value={rangeOrNote(enzyme.pH_min, enzyme.pH_max)} />
          <MetaRow label="Temperature optimum" value={fmt(enzyme.T_opt, "°C")} />
          <MetaRow label="Temperature range" value={rangeOrNote(enzyme.T_min, enzyme.T_max, "°C")} />
          <MetaRow
            label="Salinity tolerance"
            value={enzyme.salinity_evidence ? rangeOrNote(enzyme.salinity_min, enzyme.salinity_max, "%") : "Unknown"}
          />
        </div>

        <div className="detail-side">
          <div className="card sequence-card">
            <h3>Amino acid sequence</h3>
            {enzyme.has_sequence ? (
              <SequenceBlock sequence={enzyme.sequence} />
            ) : (
              <p className="no-sequence-note">
                Sequence not available in this MVP package. Mutation analysis requires a known sequence.
              </p>
            )}
            <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
              <button
                className="btn btn-accent"
                disabled={!enzyme.mutation_analysis_available}
                onClick={() => navigate(`/enzyme/${enzyme.enzyme_id}/mutations`)}
              >
                Analyze Mutations
              </button>
              <button
                className="btn btn-primary"
                onClick={() => navigate(`/simulate/${enzyme.enzyme_id}`)}
              >
                Simulate
              </button>
            </div>
            {!enzyme.mutation_analysis_available && (
              <p className="no-sequence-note" style={{ marginTop: 8 }}>
                Unavailable — no verified sequence on file for this enzyme.
              </p>
            )}
          </div>

          {enzyme.notes && (
            <div className="card notes-card">
              <h3>Notes &amp; sources</h3>
              <p>{enzyme.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value, mono }) {
  return (
    <div className="meta-row">
      <span className="meta-label">{label}</span>
      <span className={`meta-value${mono ? " mono" : ""}`}>{value ?? "—"}</span>
    </div>
  );
}

function fmt(v, unit = "") {
  if (v === null || v === undefined || Number.isNaN(v)) return "not documented";
  return `${v}${unit}`;
}

function rangeOrNote(min, max, unit = "") {
  if (min === null || min === undefined || max === null || max === undefined) {
    return "not documented (default tolerance window used)";
  }
  return `${min}–${max}${unit}`;
}
