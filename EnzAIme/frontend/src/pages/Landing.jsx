import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import PipelineDiagram from "../components/PipelineDiagram";
import "./Landing.css";

export default function Landing() {
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    api.metadata().then(setMeta).catch(() => {});
  }, []);

  return (
    <div className="landing">
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <p className="eyebrow">Environment-aware enzyme recommendation</p>
            <h1>
              Match a <em>plastic</em>, a <em>pH</em>, and a <em>temperature</em>
              <br />to the enzyme built for it.
            </h1>
            <p className="hero-sub">
              ENZAIme is an in-silico decision-support system for plastic-degrading enzymes.
              Describe the pollutant and the operating environment — pH, temperature, salinity —
              and it ranks candidate enzymes by a transparent, environment-aware compatibility
              score, then prioritizes point mutations for the one you choose.
            </p>
            <div className="hero-actions">
              <Link to="/recommend" className="btn btn-accent">Start a recommendation</Link>
              <Link to="/about" className="btn btn-ghost">How the scoring works</Link>
            </div>
            {meta && (
              <p className="hero-meta mono">
                {meta.n_enzymes_loaded} candidate enzymes loaded · {meta.supported_pollutants.join(" / ")} ·
                {" "}{meta.scoring_mode === "ai_model" ? "AI model active" : "compatibility engine active"}
              </p>
            )}
          </div>
          <PipelineDiagram />
        </div>
      </section>

      <section className="container feature-row">
        <FeatureCard
          kicker="01 — Input"
          title="Describe the environment"
          body="Pollutant, pH, temperature and salinity — the four variables that actually determine whether an enzyme will function in the field, not just in a test tube."
        />
        <FeatureCard
          kicker="02 — Scoring"
          title="Transparent compatibility"
          body="Every recommendation ships with its full breakdown: pollutant evidence, pH fit, temperature fit, salinity status. No black box, no hidden assumptions."
        />
        <FeatureCard
          kicker="03 — Mutation"
          title="Prioritize point mutations"
          body="Pick a recommended enzyme and generate ranked single-point substitution candidates for further wet-lab investigation."
        />
      </section>

      <section className="container disclaimer-strip">
        <p>
          <strong>Scientific positioning.</strong> ENZAIme does not claim to experimentally prove
          degradation. Scores are project-defined computational compatibility estimates built from
          documented enzyme properties and a frozen ESM-2 protein representation where available.
          Structural/docking validation is future work.
        </p>
      </section>
    </div>
  );
}

function FeatureCard({ kicker, title, body }) {
  return (
    <div className="feature-card card">
      <p className="eyebrow">{kicker}</p>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
