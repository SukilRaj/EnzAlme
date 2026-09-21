import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import "./Recommend.css";

const POLLUTANTS = [
  { value: "PET", label: "PET — polyethylene terephthalate" },
  { value: "PUR", label: "PUR — polyurethane" },
  { value: "PA", label: "PA — polyamide (nylon)" },
];

const DEMO_SCENARIOS = [
  { name: "Scenario 1 — PET, mild alkaline", pollutant: "PET", ph: 8.0, temperature: 35, salinity: 0.5 },
  { name: "Scenario 2 — PET, neutral & warm", pollutant: "PET", ph: 7.0, temperature: 45, salinity: 1.0 },
  { name: "Scenario 3 — PA, neutral", pollutant: "PA", ph: 7.0, temperature: 35, salinity: 0.0 },
  { name: "Scenario 4 — PUR, ambient", pollutant: "PUR", ph: 7.5, temperature: 30, salinity: 0.0 },
];

export default function Recommend() {
  const [form, setForm] = useState({ pollutant: "PET", ph: "8.0", temperature: "35", salinity: "0.5" });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);
  const navigate = useNavigate();

  function validate(values) {
    const e = {};
    const ph = parseFloat(values.ph);
    const temp = parseFloat(values.temperature);
    const sal = parseFloat(values.salinity);

    if (!POLLUTANTS.some((p) => p.value === values.pollutant)) e.pollutant = "Select a supported pollutant.";
    if (Number.isNaN(ph)) e.ph = "Enter a numeric pH value.";
    else if (ph < 0 || ph > 14) e.ph = "pH must be between 0 and 14.";
    if (Number.isNaN(temp)) e.temperature = "Enter a numeric temperature.";
    else if (temp < -10 || temp > 120) e.temperature = "Temperature must be between -10°C and 120°C.";
    if (Number.isNaN(sal)) e.salinity = "Enter a numeric salinity value.";
    else if (sal < 0) e.salinity = "Salinity cannot be negative.";
    else if (sal > 10) e.salinity = "Salinity must be 10 or below for this MVP.";
    return e;
  }

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function applyScenario(s) {
    setForm({ pollutant: s.pollutant, ph: String(s.ph), temperature: String(s.temperature), salinity: String(s.salinity) });
    setErrors({});
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const validation = validate(form);
    setErrors(validation);
    setApiError(null);
    if (Object.keys(validation).length > 0) return;

    const payload = {
      pollutant: form.pollutant,
      ph: parseFloat(form.ph),
      temperature: parseFloat(form.temperature),
      salinity: parseFloat(form.salinity),
    };

    setSubmitting(true);
    try {
      const result = await api.recommend(payload);
      navigate("/results", { state: { result } });
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Unexpected error contacting the API.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="container recommend-page">
      <p className="eyebrow">Step 1 of 2</p>
      <h1>Describe the environment</h1>
      <p className="recommend-intro">
        Enter the pollutant and the operating conditions. ENZAIme filters candidate enzymes by
        documented pollutant activity, then scores pH, temperature and salinity fit against each
        enzyme's reported tolerance.
      </p>

      <div className="recommend-grid">
        <form className="card recommend-form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="pollutant">Pollutant</label>
            <select id="pollutant" value={form.pollutant} onChange={(e) => update("pollutant", e.target.value)}>
              {POLLUTANTS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            {errors.pollutant && <span className="field-error">{errors.pollutant}</span>}
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="ph">pH</label>
              <input id="ph" type="number" step="0.1" min="0" max="14" value={form.ph} onChange={(e) => update("ph", e.target.value)} />
              {errors.ph && <span className="field-error">{errors.ph}</span>}
            </div>
            <div className="field">
              <label htmlFor="temperature">Temperature (°C)</label>
              <input id="temperature" type="number" step="1" value={form.temperature} onChange={(e) => update("temperature", e.target.value)} />
              {errors.temperature && <span className="field-error">{errors.temperature}</span>}
            </div>
            <div className="field">
              <label htmlFor="salinity">Salinity (%)</label>
              <input id="salinity" type="number" step="0.1" min="0" value={form.salinity} onChange={(e) => update("salinity", e.target.value)} />
              {errors.salinity && <span className="field-error">{errors.salinity}</span>}
            </div>
          </div>

          {apiError && (
            <div className="error-panel" style={{ marginBottom: 18 }}>
              <h3>Couldn't get recommendations</h3>
              <p>{apiError}</p>
            </div>
          )}

          <button type="submit" className="btn btn-accent" disabled={submitting}>
            {submitting ? "Analyzing…" : "Analyze & Recommend"}
          </button>
        </form>

        <aside className="scenario-panel">
          <p className="eyebrow">Demo scenarios</p>
          <p className="scenario-intro">
            Software demonstration presets — not experimental observations.
          </p>
          <div className="scenario-list">
            {DEMO_SCENARIOS.map((s) => (
              <button type="button" key={s.name} className="scenario-btn" onClick={() => applyScenario(s)}>
                <span>{s.name}</span>
                <span className="mono scenario-btn-values">
                  {s.pollutant} · pH {s.ph} · {s.temperature}°C · {s.salinity}%
                </span>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
