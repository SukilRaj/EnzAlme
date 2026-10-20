import { useEffect, useState } from 'react'
import './App.css'
import MutationWorkspace from './MutationWorkspace'
import NeuralWorkspace from './NeuralWorkspace'

const API_BASE = 'http://127.0.0.1:8000/api'
const LEGACY_MODEL_NAME = 'ESM-2 + Environment Ridge (legacy research model)'
const LEGACY_MODEL_LINEAGE = 'Exact training/evaluation row membership is unresolved. The model is not established as trained on the confirmed 221-row dataset.'

function apiErrorMessage(payload, fallback) {
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((error) => {
      const field = error.loc?.filter((part) => part !== 'body').join('.')
      return `${field ? `${field}: ` : ''}${error.msg || fallback}`
    }).join('; ') || fallback
  }
  return fallback
}

const researchMetrics = [
  { config: 'A', label: 'Environment only', mae: 1423.1084, rmse: 3200.7687, r2: -0.2917, spearman: 0.3132 },
  { config: 'B', label: 'ESM-2 only', mae: 1918.2932, rmse: 3943.4204, r2: -86.8720, spearman: -0.2268 },
  { config: 'C', label: 'ESM-2 + environment', mae: 1592.1209, rmse: 3452.4825, r2: -23.2216, spearman: 0.2394 },
]

const navigation = [
  { id: 'overview', label: 'Overview', number: '01' },
  { id: 'predict', label: 'Predict', number: '02' },
  { id: 'explore', label: 'Explore candidates', number: '03' },
  { id: 'evaluate', label: 'Research evaluation', number: '04' },
  { id: 'evidence', label: 'Evidence & limits', number: '05' },
  { id: 'mutations', label: 'Mutation & structure', number: '06' },
  { id: 'neural', label: 'Neural recommendations', number: '07' },
]

function formatNumber(value, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : 'Unavailable'
}

function App() {
  const [activeSection, setActiveSection] = useState('overview')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [form, setForm] = useState({ sequence: '', ph: '8.0', temperature: '40', duration: '48' })
  const [result, setResult] = useState(null)
  const [predictionError, setPredictionError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [recommendations, setRecommendations] = useState(null)
  const [recommendationError, setRecommendationError] = useState('')
  const [isRecommendationLoading, setIsRecommendationLoading] = useState(false)
  const [evaluation, setEvaluation] = useState(null)
  const [crossValidation, setCrossValidation] = useState(null)
  const [evaluationError, setEvaluationError] = useState('')
  const [isEvaluationLoading, setIsEvaluationLoading] = useState(true)

  useEffect(() => {
    const loadEvaluation = async () => {
      try {
        const [evaluationResponse, validationResponse] = await Promise.all([
          fetch(`${API_BASE}/evaluation`),
          fetch(`${API_BASE}/cross-validation`),
        ])
        if (!evaluationResponse.ok || !validationResponse.ok) {
          throw new Error('Saved evaluation results are unavailable.')
        }
        setEvaluation(await evaluationResponse.json())
        setCrossValidation(await validationResponse.json())
      } catch (error) {
        setEvaluationError(error instanceof TypeError
          ? 'The research evaluation service is unavailable.'
          : error.message)
      } finally {
        setIsEvaluationLoading(false)
      }
    }
    loadEvaluation()
  }, [])

  const navigateTo = (section) => {
    setActiveSection(section)
    setMobileMenuOpen(false)
    document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleChange = ({ target }) => {
    setForm((current) => ({ ...current, [target.name]: target.value }))
  }

  const validateForm = () => {
    const sequence = form.sequence.trim().toUpperCase()
    if (!sequence || !/^[ACDEFGHIKLMNPQRSTVWY]+$/.test(sequence)) {
      return 'Enter a protein sequence using standard one-letter amino-acid codes.'
    }
    if (!form.ph || Number(form.ph) < 0 || Number(form.ph) > 14) return 'pH must be between 0 and 14.'
    if (!form.temperature || !Number.isFinite(Number(form.temperature))) return 'Enter a valid temperature in °C.'
    if (!form.duration || Number(form.duration) <= 0) return 'Duration must be greater than 0 hours.'
    return ''
  }

  const validateConditions = () => {
    if (!form.ph || Number(form.ph) < 0 || Number(form.ph) > 14) return 'pH must be between 0 and 14.'
    if (!form.temperature || !Number.isFinite(Number(form.temperature))) return 'Enter a valid temperature in °C.'
    if (!form.duration || Number(form.duration) <= 0) return 'Duration must be greater than 0 hours.'
    return ''
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const validationError = validateForm()
    if (validationError) {
      setPredictionError(validationError)
      setResult(null)
      return
    }
    setIsLoading(true)
    setPredictionError('')
    setResult(null)
    try {
      const response = await fetch(`${API_BASE}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sequence: form.sequence.trim(), ph: Number(form.ph), temperature: Number(form.temperature), duration: Number(form.duration) }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(apiErrorMessage(payload, 'The prediction service returned an error.'))
      setResult(payload)
    } catch (error) {
      setPredictionError(error instanceof TypeError
        ? 'Unable to connect to the prediction service. Check that the backend is running.'
        : error.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRecommendations = async () => {
    const validationError = validateConditions()
    if (validationError) {
      setRecommendationError(validationError)
      setRecommendations(null)
      return
    }
    setIsRecommendationLoading(true)
    setRecommendationError('')
    setRecommendations(null)
    try {
      const response = await fetch(`${API_BASE}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ph: Number(form.ph), temperature: Number(form.temperature), duration: Number(form.duration), top_n: 5 }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(apiErrorMessage(payload, 'The recommendation service returned an error.'))
      setRecommendations(payload)
    } catch (error) {
      setRecommendationError(error instanceof TypeError
        ? 'Unable to connect to the recommendation service.'
        : error.message)
    } finally {
      setIsRecommendationLoading(false)
    }
  }

  return (
    <div className="app-frame">
      <aside className={`sidebar ${mobileMenuOpen ? 'is-open' : ''}`} aria-label="Primary navigation">
        <div className="brand-lockup"><div className="brand-symbol" aria-hidden="true">E</div><div><strong>EnzAIme</strong><span>Research workspace</span></div></div>
        <nav id="primary-navigation"><span className="nav-caption">Workspace</span>{navigation.map((item) => <button className={activeSection === item.id ? 'nav-item active' : 'nav-item'} key={item.id} type="button" onClick={() => navigateTo(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
        <div className="sidebar-note"><span className="status-dot" aria-hidden="true" /><div><strong>Scope locked</strong><span>TPA / PET research</span></div></div>
      </aside>
      {mobileMenuOpen && <button className="mobile-scrim" type="button" aria-label="Close menu" onClick={() => setMobileMenuOpen(false)} />}
      <main className="main-content">
        <header className="topbar"><button className="menu-button" type="button" aria-expanded={mobileMenuOpen} aria-controls="primary-navigation" onClick={() => setMobileMenuOpen((open) => !open)}><span aria-hidden="true">☰</span><span className="sr-only">Toggle navigation</span></button><div className="breadcrumb"><span>EnzAIme</span><span aria-hidden="true">/</span><strong>{navigation.find((item) => item.id === activeSection)?.label}</strong></div><span className="topbar-tag">Research mode</span></header>
        <section className="hero-section" id="overview" aria-labelledby="overview-heading"><div className="hero-copy"><p className="overline">Environment-aware enzyme research</p><h1 id="overview-heading">From protein sequence<br /><em>to measurable signal.</em></h1><p className="hero-lede">A focused workspace for exploring predicted TPA concentration from PET-degrading enzyme sequences under defined assay conditions.</p><div className="hero-actions"><button type="button" className="primary-button" onClick={() => navigateTo('predict')}>Open prediction workspace <span aria-hidden="true">→</span></button><span className="hero-note">Predictions are computational estimates, not experimental results.</span></div></div><div className="hero-index" aria-hidden="true"><span>01</span><div className="index-rule" /><span>05</span></div></section>
        <section className="fact-strip" aria-label="Verified research scope"><div className="fact"><strong>221</strong><span>confirmed assay records</span></div><div className="fact"><strong>25</strong><span>unique proteins</span></div><div className="fact"><strong>TPA</strong><span>target analyte</span></div><div className="fact"><strong>PET</strong><span>substrate scope</span></div></section>
        <section className="content-section prediction-section" id="predict" aria-labelledby="predict-heading"><SectionHeading number="02" eyebrow="Prediction workspace" title="Describe an assay" id="predict-heading" /><div className="prediction-layout"><form className="research-form" onSubmit={handleSubmit}><div className="form-intro"><p>Supply a sequence and the conditions you want to inspect. All fields are sent to the existing prediction API.</p><span className="required-note">All fields required</span></div><label htmlFor="sequence">Protein sequence <span>amino-acid one-letter codes</span></label><textarea id="sequence" name="sequence" value={form.sequence} onChange={handleChange} placeholder="Paste sequence, for example: MNFPRASRLM..." rows="8" required aria-describedby="sequence-help" /><p id="sequence-help" className="field-help">Standard amino-acid codes only. The sequence is encoded by the backend's serving model.</p><div className="condition-grid"><NumberField id="temperature" label="Temperature" unit="°C" value={form.temperature} onChange={handleChange} min="-273.2" step="0.1" /><NumberField id="ph" label="pH" unit="pH" value={form.ph} onChange={handleChange} min="0" max="14" step="0.1" /><NumberField id="duration" label="Duration" unit="hours" value={form.duration} onChange={handleChange} min="0.1" step="0.1" /></div>{predictionError && <p className="alert error" role="alert">{predictionError}</p>}<button className="primary-button full-button" type="submit" disabled={isLoading}>{isLoading ? 'Running prediction…' : 'Run prediction'}<span aria-hidden="true">→</span></button><p className="model-disclosure">Serving model: <strong>{result?.model || LEGACY_MODEL_NAME}</strong>. {result?.lineage_note || LEGACY_MODEL_LINEAGE}</p></form><div className={`result-card ${result ? 'has-result' : ''}`} aria-live="polite" aria-labelledby="result-heading"><div className="result-card-top"><span className="card-kicker">Output / µM</span><span className="live-label"><i /> API result</span></div>{result ? <div className="result-success"><p id="result-heading">Predicted TPA concentration</p><div className="result-number">{formatNumber(Number(result.predicted_activity_um))}<small>µM</small></div><p className="result-context">Under the supplied PET assay conditions. This estimate is not a universal enzyme activity score.</p><div className="result-meta"><Meta label="Target" value={result.target || 'TPA'} /><Meta label="Substrate" value={result.substrate || 'PET'} /><Meta label="pH" value={result.conditions?.ph ?? form.ph} /><Meta label="Temperature" value={`${result.conditions?.temperature ?? form.temperature} °C`} /><Meta label="Duration" value={`${result.conditions?.duration ?? form.duration} h`} /></div></div> : <div className="result-empty"><span className="empty-glyph" aria-hidden="true">↗</span><h3 id="result-heading">Your result will appear here.</h3><p>Complete the assay inputs to request a prediction from the connected backend.</p></div>}</div></div></section>
        <section className="content-section explore-section" id="explore" aria-labelledby="explore-heading"><SectionHeading number="03" eyebrow="Candidate exploration" title="Explore available proteins" id="explore-heading" /><div className="section-lede-row"><p>Scores come from the legacy research model. Evidence counts come from confirmed TPA/PET records; they do not establish the model’s training dataset. Rankings are exploratory computational comparisons requiring experimental validation.</p><button className="secondary-button" type="button" onClick={handleRecommendations} disabled={isRecommendationLoading}>{isRecommendationLoading ? 'Ranking…' : 'Rank candidates'}<span aria-hidden="true">↗</span></button></div>{recommendationError && <p className="alert error" role="alert">{recommendationError}</p>}{isRecommendationLoading && <StateBlock title="Ranking candidates" detail="Waiting for the existing recommendation service." />}{!isRecommendationLoading && !recommendations && !recommendationError && <StateBlock title="No ranking loaded" detail="Use the current assay conditions to request the supported candidate ranking." />}{!isRecommendationLoading && recommendations && <div className="recommendation-output"><div className="conditions-line"><span>{recommendations.target} / {recommendations.substrate}</span><span>pH {recommendations.conditions.ph} · {recommendations.conditions.temperature} °C · {recommendations.conditions.duration} h</span></div><div className="candidate-list">{recommendations.recommendations?.length ? recommendations.recommendations.map((item) => <CandidateCard key={item.protein_id} item={item} />) : <StateBlock title="No candidates returned" detail="The recommendation service returned an empty result." />}</div></div>}</section>
        <section className="content-section evaluation-section" id="evaluate" aria-labelledby="evaluate-heading"><SectionHeading number="04" eyebrow="Research evaluation" title="Read the evidence in context" id="evaluate-heading" /><div className="evaluation-callout"><span className="callout-mark">i</span><p>The API reports saved evaluation for the legacy research model with 227 records in its metadata. Exact training/evaluation row membership is unresolved. The A/B/C table is a separate experiment on the confirmed 221-row dataset; it does not validate the served model. Neither is experimental validation.</p></div>{isEvaluationLoading && <StateBlock title="Loading saved evaluation" detail="Reading the existing evaluation endpoints." />}{!isEvaluationLoading && evaluationError && <p className="alert warning" role="alert">{evaluationError} No substitute metrics are shown.</p>}{!isEvaluationLoading && !evaluationError && evaluation && <div className="evaluation-stack"><div className="serving-model"><div><span className="card-kicker">Currently served legacy research model</span><h3>{evaluation.model}</h3></div><span className="model-status">API connected</span></div><div className="metric-grid"><Metric label="Reported legacy records" value={evaluation.training_records} /><Metric label="Unique proteins" value={evaluation.unique_proteins} /><Metric label="Reported split" value="Protein-grouped" /><Metric label="Folds" value={evaluation.cross_validation?.folds} /></div><div className="api-metrics"><div className="block-heading"><div><span className="card-kicker">Reported legacy evaluation</span><h3>Mean ± variation</h3></div></div><div className="api-metric-values"><Metric label="MAE" value={`${formatNumber(evaluation.cross_validation.mae.mean)} µM`} sub={`± ${formatNumber(evaluation.cross_validation.mae.std)} µM`} /><Metric label="RMSE" value={`${formatNumber(evaluation.cross_validation.rmse.mean)} µM`} sub={`± ${formatNumber(evaluation.cross_validation.rmse.std)} µM`} /><Metric label="R²" value={formatNumber(evaluation.cross_validation.r2.mean, 4)} sub={`± ${formatNumber(evaluation.cross_validation.r2.std, 4)}`} /><Metric label="Spearman" value={formatNumber(evaluation.cross_validation.spearman.mean, 4)} sub={`± ${formatNumber(evaluation.cross_validation.spearman.std, 4)}`} /></div></div>{crossValidation && <FoldChart folds={crossValidation.folds} />}</div>}{<div className="ablation-block"><div className="block-heading"><div><span className="card-kicker">Archived Step 3 experiment</span><h3>Controlled A / B / C ablation</h3></div><span className="archive-label">221 records · 25 proteins</span></div><p className="block-description">Same protein-grouped folds, preprocessing discipline, and Ridge model. These are mean fold metrics; pooled OOF values are shown separately.</p><div className="table-scroll"><table><caption className="sr-only">Controlled ablation mean fold metrics</caption><thead><tr><th>Configuration</th><th>Feature block</th><th>MAE (µM)</th><th>RMSE (µM)</th><th>R²</th><th>Spearman</th></tr></thead><tbody>{researchMetrics.map((item) => <tr key={item.config}><td><strong>{item.config}</strong></td><td>{item.label}</td><td>{formatNumber(item.mae, 1)}</td><td>{formatNumber(item.rmse, 1)}</td><td>{item.r2.toFixed(4)}</td><td>{item.config === 'B' ? <>{item.spearman.toFixed(4)}<small className="table-note">4/5 defined folds</small></> : item.spearman.toFixed(4)}</td></tr>)}</tbody></table></div><p className="table-footnote">B's mean fold Spearman uses 4 defined folds out of 5 because one fold had constant predictions. Metrics are descriptive and do not select a production model.</p></div>}</section>
        <section className="content-section evidence-section-main" id="evidence" aria-labelledby="evidence-heading"><SectionHeading number="05" eyebrow="Evidence & limitations" title="What this workspace can support" id="evidence-heading" /><div className="evidence-columns"><EvidenceItem title="Provenance" text="The confirmed research set contains 221 retained TPA/PET assay records across 25 proteins. Some measurements are digitized or converted from reported units and retain their source context." /><EvidenceItem title="Generalization" text="Protein-grouped validation keeps proteins separate between train and test. Fold results vary substantially, so performance should not be read as a universal activity claim." /><EvidenceItem title="Boundaries" text="Candidate rankings and predictions are computational. Sequence variants and structural context can be inspected here; mutation effects, industrial performance, and experimental confirmation remain unvalidated." /></div></section>
        <MutationWorkspace apiBase={API_BASE} />
        <NeuralWorkspace />
        <footer><span>EnzAIme / TPA · PET</span><span>Research interface · no production selection</span></footer>
      </main>
    </div>
  )
}

function SectionHeading({ number, eyebrow, title, id }) { return <div className="section-heading"><span className="section-number">{number}</span><div><p className="overline">{eyebrow}</p><h2 id={id}>{title}</h2></div></div> }
function NumberField({ id, label, unit, value, onChange, ...props }) { return <div className="number-field"><label htmlFor={id}>{label}</label><div><input id={id} name={id} type="number" value={value} onChange={onChange} required {...props} /><span>{unit}</span></div></div> }
function Meta({ label, value }) { return <div><span>{label}</span><strong>{value}</strong></div> }
function Metric({ label, value, sub }) { return <div className="metric"><span>{label}</span><strong>{value}</strong>{sub && <small>{sub}</small>}</div> }
function StateBlock({ title, detail }) { return <div className="state-block" role="status"><span className="state-line" aria-hidden="true" /><h3>{title}</h3><p>{detail}</p></div> }
function CandidateCard({ item }) { const evidence = item.evidence || {}; return <article className="candidate-card"><div className="candidate-rank">#{item.rank}</div><div className="candidate-main"><div><h3>{item.protein_name}</h3><span>Protein ID {item.protein_id}</span></div><strong>{formatNumber(Number(item.predicted_activity_um))}<small> µM predicted</small></strong></div><div className="candidate-evidence"><span>Sequence {evidence.sequence_available ? 'available' : 'not available'}</span><span>Embedding {evidence.esm2_embedding_available ? 'available' : 'not available'}</span><span>{evidence.experimental_activity_records ?? 0} confirmed TPA/PET records</span></div><p className="candidate-note">Evidence source: {evidence.source}</p><p className="candidate-note">{item.prediction_status}. {item.validation_note}</p></article> }
function FoldChart({ folds }) { const maxValue = Math.max(...folds.map((fold) => Math.max(fold.mae, fold.rmse))); return <div className="fold-chart"><div className="block-heading"><div><span className="card-kicker">Reported legacy fold results</span><h3>Fold error profile</h3></div><span className="archive-label">µM · lower is better</span></div><div className="fold-bars">{folds.map((fold) => <div className="fold-row" key={fold.fold}><strong>F{fold.fold}</strong><div className="bar-set"><div><span>MAE</span><i style={{ width: `${(fold.mae / maxValue) * 100}%` }} /></div><div><span>RMSE</span><i className="rmse-bar" style={{ width: `${(fold.rmse / maxValue) * 100}%` }} /></div></div><small>{formatNumber(fold.rmse, 0)}</small></div>)}</div><p className="chart-note">Protein-grouped folds can vary when held-out protein groups have different record counts and target ranges.</p></div> }
function EvidenceItem({ title, text }) { return <article className="evidence-item-main"><span className="evidence-icon" aria-hidden="true">+</span><h3>{title}</h3><p>{text}</p></article> }

export default App
