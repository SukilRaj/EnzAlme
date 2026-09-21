import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import ScoreDial from "../components/ScoreDial";
import CompatMeter from "../components/CompatMeter";
import "./Simulate.css";

const DISCLAIMER_TEXT =
  "Live exploration of the same Environment-Aware Suitability Score used in /recommend — not a new prediction, not experimental data.";

export default function Simulate() {
  const { enzymeId } = useParams();
  const [enzyme, setEnzyme] = useState(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [error, setError] = useState(null);

  // Sliders state
  const [sliders, setSliders] = useState({ ph: 7.0, temperature: 35.0, salinity: 0.5 });
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  // Sweep states
  const [phSweep, setPhSweep] = useState([]);
  const [tempSweep, setTempSweep] = useState([]);
  const [salSweep, setSalSweep] = useState([]);
  const [sweepLoading, setSweepLoading] = useState({ ph: false, temperature: false, salinity: false });

  const debounceTimerRef = useRef(null);

  const runSimulation = useCallback(async (currentSliders, enzymeData) => {
    if (!enzymeData) return;
    setSimulating(true);
    try {
      const res = await api.simulate({
        enzyme_id: enzymeData.enzyme_id,
        pollutant: enzymeData.pollutant || "PET",
        ph: currentSliders.ph,
        temperature: currentSliders.temperature,
        salinity: currentSliders.salinity,
      });
      setSimResult(res);
    } catch (err) {
      console.error("Simulation error:", err);
    } finally {
      setSimulating(false);
    }
  }, []);

  const fetchSweep = useCallback(async (variable, currentSliders, enzymeData) => {
    if (!enzymeData) return;
    setSweepLoading((prev) => ({ ...prev, [variable]: true }));
    let sweepMin = 0.0;
    let sweepMax = 14.0;
    if (variable === "temperature") {
      sweepMin = -10.0;
      sweepMax = 120.0;
    } else if (variable === "salinity") {
      sweepMin = 0.0;
      sweepMax = 10.0;
    }

    try {
      const points = await api.simulateSweep({
        enzyme_id: enzymeData.enzyme_id,
        pollutant: enzymeData.pollutant || "PET",
        sweep_variable: variable,
        sweep_min: sweepMin,
        sweep_max: sweepMax,
        steps: 40,
        fixed_ph: currentSliders.ph,
        fixed_temperature: currentSliders.temperature,
        fixed_salinity: currentSliders.salinity,
      });

      if (variable === "ph") setPhSweep(points);
      else if (variable === "temperature") setTempSweep(points);
      else if (variable === "salinity") setSalSweep(points);
    } catch (err) {
      console.error(`Sweep error (${variable}):`, err);
    } finally {
      setSweepLoading((prev) => ({ ...prev, [variable]: false }));
    }
  }, []);

  // Initial load
  useEffect(() => {
    let active = true;
    setLoadingInitial(true);
    setError(null);

    api
      .getEnzyme(enzymeId)
      .then((data) => {
        if (!active) return;
        setEnzyme(data);

        // Initialize to reported optimums or midpoints
        const initPh =
          data.pH_opt !== null && data.pH_opt !== undefined && !Number.isNaN(data.pH_opt)
            ? Number(data.pH_opt)
            : 7.0;
        const initTemp =
          data.T_opt !== null && data.T_opt !== undefined && !Number.isNaN(data.T_opt)
            ? Number(data.T_opt)
            : 35.0;
        const initSal = 0.5;

        const initialSliders = { ph: initPh, temperature: initTemp, salinity: initSal };
        setSliders(initialSliders);

        // Initial simulation and sweeps
        runSimulation(initialSliders, data);
        fetchSweep("ph", initialSliders, data);
        fetchSweep("temperature", initialSliders, data);
        fetchSweep("salinity", initialSliders, data);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load enzyme details.");
      })
      .finally(() => {
        if (active) setLoadingInitial(false);
      });

    return () => {
      active = false;
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [enzymeId, runSimulation, fetchSweep]);

  // Handle slider changes with 150ms debounce
  const handleSliderChange = (variable, value) => {
    const num = parseFloat(value);
    const updated = { ...sliders, [variable]: num };
    setSliders(updated);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      if (!enzyme) return;
      // 1. Run simulation point
      runSimulation(updated, enzyme);

      // 2. Refetch the OTHER two sweeps only
      if (variable === "ph") {
        fetchSweep("temperature", updated, enzyme);
        fetchSweep("salinity", updated, enzyme);
      } else if (variable === "temperature") {
        fetchSweep("ph", updated, enzyme);
        fetchSweep("salinity", updated, enzyme);
      } else if (variable === "salinity") {
        fetchSweep("ph", updated, enzyme);
        fetchSweep("temperature", updated, enzyme);
      }
    }, 150);
  };

  if (loadingInitial) {
    return (
      <div className="container" style={{ padding: "80px 28px", textAlign: "center" }}>
        <p className="eyebrow">Loading simulator...</p>
        <h2>Initializing Environmental Sensitivity Simulator</h2>
      </div>
    );
  }

  if (error || !enzyme) {
    return (
      <div className="container" style={{ padding: "80px 28px", textAlign: "center" }}>
        <h2>Unable to load enzyme</h2>
        <p>{error || "Enzyme record not found."}</p>
        <Link to="/recommend" className="btn btn-primary" style={{ marginTop: 16 }}>
          Return to Recommend
        </Link>
      </div>
    );
  }

  const scorePercent = simResult ? simResult.score_percent : 0;
  const breakdown = simResult ? simResult.breakdown : { pollutant: 0, ph: 0, temperature: 0, salinity: 0 };
  const explanation = simResult ? simResult.explanation : null;

  return (
    <div className="container simulate-page">
      <div className="simulate-header">
        <Link to={`/enzyme/${enzyme.enzyme_id}`} className="simulate-back-link">
          ← Back to {enzyme.enzyme_name || enzyme.enzyme_id}
        </Link>
        <div className="simulate-header-row">
          <div>
            <p className="eyebrow">Interactive Explorer</p>
            <h1>Environmental Sensitivity Simulator</h1>
            <p style={{ margin: 0 }}>
              Testing <strong>{enzyme.enzyme_name}</strong> ({enzyme.enzyme_id}) against{" "}
              <strong>{enzyme.pollutant || "Target pollutant"}</strong>
            </p>
          </div>
        </div>
      </div>

      <div className="simulate-grid">
        {/* Sliders panel */}
        <div className="simulate-controls-card">
          <h2 className="simulate-controls-title">Operating Conditions</h2>

          <div className="slider-group">
            <div className="slider-header">
              <label htmlFor="ph-slider" className="slider-label">
                pH
              </label>
              <span className="slider-value mono">{sliders.ph.toFixed(1)}</span>
            </div>
            <input
              id="ph-slider"
              type="range"
              className="slider-range-input"
              min="0"
              max="14"
              step="0.1"
              value={sliders.ph}
              onChange={(e) => handleSliderChange("ph", e.target.value)}
            />
            <div className="slider-bounds mono">
              <span>0.0 (Acidic)</span>
              <span>7.0 (Neutral)</span>
              <span>14.0 (Alkaline)</span>
            </div>
          </div>

          <div className="slider-group">
            <div className="slider-header">
              <label htmlFor="temp-slider" className="slider-label">
                Temperature
              </label>
              <span className="slider-value mono">{sliders.temperature.toFixed(0)}°C</span>
            </div>
            <input
              id="temp-slider"
              type="range"
              className="slider-range-input"
              min="-10"
              max="120"
              step="1"
              value={sliders.temperature}
              onChange={(e) => handleSliderChange("temperature", e.target.value)}
            />
            <div className="slider-bounds mono">
              <span>-10°C</span>
              <span>55°C</span>
              <span>120°C</span>
            </div>
          </div>

          <div className="slider-group">
            <div className="slider-header">
              <label htmlFor="sal-slider" className="slider-label">
                Salinity
              </label>
              <span className="slider-value mono">{sliders.salinity.toFixed(1)}%</span>
            </div>
            <input
              id="sal-slider"
              type="range"
              className="slider-range-input"
              min="0"
              max="10"
              step="0.1"
              value={sliders.salinity}
              onChange={(e) => handleSliderChange("salinity", e.target.value)}
            />
            <div className="slider-bounds mono">
              <span>0.0% (Fresh)</span>
              <span>3.5% (Seawater)</span>
              <span>10.0% (Hypersaline)</span>
            </div>
          </div>
        </div>

        {/* Live Score Dial & Breakdown */}
        <div className="simulate-output-card">
          <div className="score-dial-container">
            <div className={simulating ? "score-dial-pulsing" : ""}>
              <ScoreDial percent={scorePercent} size={130} label="Suitability Score" />
            </div>
          </div>

          {/* Persistent Disclaimer */}
          <div className="simulate-disclaimer-badge">
            {DISCLAIMER_TEXT}
          </div>

          <div className="meters-list">
            <CompatMeter
              label="Pollutant match"
              value={breakdown.pollutant}
              note={explanation?.pollutant?.note}
            />
            <CompatMeter
              label="pH compatibility"
              value={breakdown.ph}
              note={explanation?.ph?.reported_range}
            />
            <CompatMeter
              label="Temperature fit"
              value={breakdown.temperature}
              note={explanation?.temperature?.reported_range}
            />
            <CompatMeter
              label="Salinity tolerance"
              value={breakdown.salinity}
              status={simResult?.salinity_status}
              note={explanation?.salinity?.note}
            />
          </div>
        </div>
      </div>

      {/* Sensitivity Sweeps Section */}
      <div className="sensitivity-section">
        <div className="sensitivity-section-head">
          <h2 className="sensitivity-section-title">Sensitivity Sweeps</h2>
          <p className="sensitivity-section-desc">
            Varying one environmental variable while holding the other two at current slider values.
            The amber dashed line indicates current slider position.
          </p>
        </div>

        <div className="sensitivity-charts-grid">
          <SensitivityChart
            title="pH Sensitivity"
            points={phSweep}
            currentValue={sliders.ph.toFixed(1)}
            unit=""
            minVal={0}
            maxVal={14}
            loading={sweepLoading.ph}
          />
          <SensitivityChart
            title="Temperature Sensitivity"
            points={tempSweep}
            currentValue={sliders.temperature.toFixed(0)}
            unit="°C"
            minVal={-10}
            maxVal={120}
            loading={sweepLoading.temperature}
          />
          <SensitivityChart
            title="Salinity Sensitivity"
            points={salSweep}
            currentValue={sliders.salinity.toFixed(1)}
            unit="%"
            minVal={0}
            maxVal={10}
            loading={sweepLoading.salinity}
          />
        </div>
      </div>
    </div>
  );
}

function SensitivityChart({ title, points, currentValue, unit, minVal, maxVal, loading }) {
  const width = 280;
  const height = 150;
  const padLeft = 36;
  const padRight = 16;
  const padTop = 16;
  const padBottom = 26;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const numCur = parseFloat(currentValue);
  const xFor = (v) => padLeft + Math.max(0, Math.min(1, (v - minVal) / (maxVal - minVal))) * plotW;
  const yFor = (s) => padTop + (1 - Math.max(0, Math.min(1, s))) * plotH;

  const polylineStr =
    points && points.length > 0
      ? points.map((p) => `${xFor(p.value).toFixed(1)},${yFor(p.suitability_score).toFixed(1)}`).join(" ")
      : "";

  const curX = Number.isNaN(numCur) ? padLeft : xFor(numCur);

  return (
    <div className="sensitivity-chart-card">
      <div className="sensitivity-chart-head">
        <span className="sensitivity-chart-title">{title}</span>
        <span className="sensitivity-chart-val mono">
          {currentValue}
          {unit}
        </span>
      </div>
      <div className={`sensitivity-chart-svg-wrap ${loading ? "chart-loading" : ""}`}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img">
          {/* Background grid */}
          <line
            x1={padLeft}
            y1={padTop}
            x2={padLeft + plotW}
            y2={padTop}
            stroke="var(--line)"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
          <line
            x1={padLeft}
            y1={padTop + plotH / 2}
            x2={padLeft + plotW}
            y2={padTop + plotH / 2}
            stroke="var(--line)"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
          <line
            x1={padLeft}
            y1={padTop + plotH}
            x2={padLeft + plotW}
            y2={padTop + plotH}
            stroke="var(--line)"
            strokeWidth="1"
          />
          <line
            x1={padLeft}
            y1={padTop}
            x2={padLeft}
            y2={padTop + plotH}
            stroke="var(--line)"
            strokeWidth="1"
          />

          {/* Y Axis labels */}
          <text
            x={padLeft - 6}
            y={padTop + 4}
            textAnchor="end"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--slate-2)"
          >
            100%
          </text>
          <text
            x={padLeft - 6}
            y={padTop + plotH / 2 + 3}
            textAnchor="end"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--slate-2)"
          >
            50%
          </text>
          <text
            x={padLeft - 6}
            y={padTop + plotH}
            textAnchor="end"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--slate-2)"
          >
            0%
          </text>

          {/* X Axis labels */}
          <text
            x={padLeft}
            y={padTop + plotH + 15}
            textAnchor="start"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--slate-2)"
          >
            {minVal}
            {unit}
          </text>
          <text
            x={padLeft + plotW}
            y={padTop + plotH + 15}
            textAnchor="end"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--slate-2)"
          >
            {maxVal}
            {unit}
          </text>

          {/* Curve */}
          {polylineStr && (
            <polyline
              fill="none"
              stroke="var(--moss)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={polylineStr}
            />
          )}

          {/* Current position vertical marker line */}
          <line
            x1={curX}
            y1={padTop}
            x2={curX}
            y2={padTop + plotH}
            stroke="var(--amber-deep)"
            strokeWidth="2"
            strokeDasharray="3 2"
          />
          <circle cx={curX} cy={padTop + 3} r="3" fill="var(--amber-deep)" />
        </svg>
      </div>
    </div>
  );
}
