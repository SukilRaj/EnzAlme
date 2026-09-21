import "./About.css";

export default function About() {
  return (
    <div className="container about-page">
      <p className="eyebrow">Methodology</p>
      <h1>How ENZAIme scores an enzyme</h1>
      <p className="about-intro">
        ENZAIme is an in-silico decision-support tool, not an experimental degradation predictor.
        Every number it shows is either a documented literature/database value, or a transparent
        formula applied to those values. Nothing is hidden.
      </p>

      <section className="about-section">
        <h2>1. Architecture</h2>
        <p>
          User input (pollutant, pH, temperature, salinity) is validated, then matched against a
          candidate enzyme database. Each enzyme's documented pollutant evidence, pH/temperature
          tolerance and (where known) salinity tolerance are combined into a per-factor
          compatibility breakdown. Where a trained model and cached ESM-2 embeddings are available,
          a small neural network refines the final score; otherwise — and by default in this MVP —
          the same transparent compatibility formula serves the score directly. Recommendations are
          ranked and the top 2–3 returned with a full explanation. Selecting an enzyme opens the
          mutation module, which generates and ranks single-point substitution candidates.
        </p>
      </section>

      <section className="about-section">
        <h2>2. Environment-Aware Suitability Score</h2>
        <p>
          For pollutant compatibility (L<sub>poll</sub>): verified activity scores 1.0, predicted or
          homologous evidence scores 0.7, no evidence scores 0.0. Enzymes with zero pollutant
          evidence are excluded before ranking.
        </p>
        <p>
          For pH and temperature, if the enzyme has a documented range and the input falls inside
          it, compatibility is 1.0. Outside the range, compatibility decays linearly to 0 over a
          configurable tolerance window (default ±2 pH units, ±20°C). If only an optimum value is
          known, the same decay is applied around a configurable window centered on that optimum.
        </p>
        <p>
          Salinity uses the same range logic when tolerance data exists. When it doesn't — the
          common case in this MVP — a neutral default of 0.8 is used, and the UI always marks the
          result <strong>"Unknown"</strong> rather than presenting it as measured.
        </p>
        <p className="about-formula mono">
          S = 0.40·L_poll + 0.25·L_pH + 0.25·L_T + 0.10·L_S, clipped to [0, 1]
        </p>
        <p>Weights are configurable and validated to sum to 1.0 at startup.</p>
      </section>

      <section className="about-section">
        <h2>3. Why ESM-2, and why frozen</h2>
        <p>
          ESM-2 provides a general-purpose protein sequence representation without requiring
          structural data. It is used strictly as a <strong>frozen encoder</strong> — mean-pooled
          per-sequence embeddings, no fine-tuning — because the verified plastic-active enzyme
          dataset available for this MVP is far too small (fewer than 100 records) to fine-tune a
          transformer without severe overfitting. ESM-2 itself is not claimed as novel; the
          project's novelty is combining protein representation with explicit environmental
          conditioning for context-specific recommendation.
        </p>
      </section>

      <section className="about-section">
        <h2>4. The label problem</h2>
        <p>
          No large matched enzyme-environment experimental suitability dataset exists publicly.
          Rather than pretend otherwise, the transparent compatibility formula above serves as the
          <strong> reference target</strong>. An optional neural model can be trained to regress
          toward this reference once enough cached embeddings and synthetic scenario labels exist —
          but the system is designed to run correctly with or without that model. If no trained
          model is present, ENZAIme automatically and visibly falls back to the compatibility
          engine (see the mode badge on every result).
        </p>
      </section>

      <section className="about-section">
        <h2>5. Mutation module</h2>
        <p>
          Single-point substitutions are generated across a bounded set of sequence positions and
          scored as <span className="mono">S_mut = 0.7·S_stability + 0.3·S_fitness_proxy</span>.
          Where a curated FireProtDB subset is available, real experimentally-derived values are
          used; otherwise a documented, deterministic heuristic (Kyte–Doolittle hydropathy, residue
          volume, helix propensity — all standard published reference tables) estimates stability
          and fitness proxies. This is explicitly a computational screening aid, not a substitute
          for experimental characterization.
        </p>
      </section>

      <section className="about-section">
        <h2>6. What's explicitly future work</h2>
        <p>
          Structural modeling and molecular docking validation of mutation candidates are out of
          scope for this MVP. An industrial wastewater-matched environmental dataset and a
          FireProtDB-backed mutation provider are designed for (via the same provider interfaces
          used today) but not yet integrated.
        </p>
      </section>
    </div>
  );
}
