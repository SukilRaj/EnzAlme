import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {marked} from 'marked';

const out=path.resolve('docs/presentation_study_guide_2026-10-12');
const md=await fs.readFile(path.join(out,'EnzAIme_Slide_by_Slide_Guide.md'),'utf8');
const inventory=JSON.parse(await fs.readFile(path.join(out,'slide_inventory.json'),'utf8'));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
// Readable Unicode equivalents let the complete guide work offline without font/CDN dependencies.
const formulas=[
'ẑ = β₀ + βᵀx',
'ŷ = max(0, exp(ẑ) − 1)',
'E ∈ ℝ^(N×3),  B ∈ ℝ^(N×1280),  zᵢ = log(1 + yᵢ),  gᵢ = pᵢ',
'{pᵢ : i ∈ Iₖᵗʳ} ∩ {pᵢ : i ∈ Iₖᵗᵉ} = ∅',
'⋃ₖ₌₁ᴷ Iₖᵗᵉ = {1,…,N};  Iₖᵗᵉ ∩ Iℓᵗᵉ = ∅ for k ≠ ℓ',
'rᵢ = yᵢ − ŷᵢ',
'MAE = (1/n) Σᵢ∈V |rᵢ|',
'RMSE = √[(1/n) Σᵢ∈V rᵢ²]',
'R² = 1 − [Σᵢ∈V rᵢ²] / [Σᵢ∈V (yᵢ − ȳᵥ)²]',
'ρₛ = Corr(rank(y), rank(ŷ))',
'M̄ = (1/|J|) Σₖ∈J Mₖ;  sₘ = √[Σₖ∈J (Mₖ − M̄)² / (|J| − 1)]',
'(1/K) Σₖ RMSEₖ ≠ √[(1/N) Σᵢ rᵢ²] in general',
'nₚ = Σᵢ₌₁ᴺ 𝟙[pᵢ = p]',
'qₚ = max(0, exp{f_L(S_L([P_L(bₚ); e*]))} − 1)\nThe subscript L identifies the legacy transforms/model.',
'yµM = v                  if u is µM or µmol/L\n     = 1000v              if u is mM\n     = 1000v / 166.13     if u is µg/mL',
'tₕₒᵤᵣₛ = t     if the reported unit is hours\n        = 24t   if the reported unit is days',
'Hₚ ∈ ℝ^(ℓₚ×1280)\nbₚ = [Σⱼ₌₁^ℓₚ aₚⱼ Hₚⱼ] / max(Σⱼ₌₁^ℓₚ aₚⱼ, ε)',
'xᵢ^(A,k) = S_(E,k)(eᵢ)',
'xᵢ^(B,k) = Pₖ(S_(B,k)(b_(pᵢ)))',
'xᵢ^(C,k) = S_(F,k)([Pₖ(S_(B,k)(b_(pᵢ))); eᵢ])',
'Sₖ(xⱼ) = (xⱼ − μₖⱼ) / sₖⱼ',
'Pₖ(u) = Wₖᵀ(u − cₖ)',
'(β̂, β̂₀) = arg min_(β,β₀) [Σᵢ∈Iₖᵗʳ (zᵢ − β₀ − xᵢᵀβ)² + λ‖β‖₂²]',
'z = log(1 + y)',
'ŷ = exp(ẑ) − 1',
'rᵢ = yᵢ − ŷᵢ;  ηₚ = [Σᵢ:ₚᵢ₌ₚ rᵢ²] / [Σᵢ rᵢ²]',
'Δᵢ^(A→C) = |yᵢ − ŷᵢᶜ| − |yᵢ − ŷᵢᴬ|',
'Uₐ ∈ {idle, loading, success, error}\na ∈ {predict, recommend, evaluate}',
'25 × 1280 × 4 = 128000 bytes = 125 KiB',
];
let formulaIndex=0;
const convert=s=>{
 const replaced=s.replace(/\$\$([\s\S]*?)\$\$/g,(_,tex)=>{
  const display=formulas[formulaIndex++];
  if(!display)throw new Error('Missing offline formula');
  return `\n<div class="formula"><pre>${esc(display)}</pre><details><summary>Equation in LaTeX</summary><code>${esc(tex.trim())}</code></details></div>\n`;
 });
 return marked.parse(replaced);
};
const chunks=md.split(/(?=^## )/m);
let main='',nav='',slides=0;
for(let i=0;i<chunks.length;i++){
 const chunk=chunks[i];
 const header=chunk.match(/^## (.+)/);
 const match=header?.[1].match(/^Slide (\d+) — (.+)/);
 const id=match?'slide-'+match[1]:'section-'+i;
 const title=header?.[1]||'Guide introduction';
 let content=convert(chunk);
 if(match){
  slides++;
  const item=inventory.find(x=>x.slide===Number(match[1]));
  const images=item.images.filter(x=>!['slide-27-3.png','slide-27-4.png'].includes(path.basename(x)));
  if(images.length){
   content+='<details class="source"><summary>View original slide figure'+(images.length>1?'s':'')+'</summary>';
   for(const img of images){ const name=path.basename(img);content+=`<a href="source_images/${name}" target="_blank"><img loading="lazy" src="source_images/${name}" alt="Original image from slide ${item.slide}"></a>`; }
   content+='</details>';
  }
  const paragraphs=item.paragraphs.filter(x=>x.trim());
  content+=`<details class="source"><summary>Original slide text (${paragraphs.length} paragraphs)</summary><p class="muted">Extracted from the original slide. Equations in this transcript may be linearized; use the explained formulas above.</p><ol>${paragraphs.map(p=>'<li>'+esc(p)+'</li>').join('')}</ol></details>`;
 }
 nav+=`<a href="#${id}" data-title="${esc(title.toLowerCase())}">${esc(title)}</a>`;
 main+=`<section id="${id}" data-title="${esc(title.toLowerCase())}">${content}</section>`;
}
if(slides!==83 || inventory.length!==83 || formulaIndex!==formulas.length)throw new Error('Coverage mismatch');
const html=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>EnzAIme · Complete 83-slide study guide</title><style>
:root{--ink:#16343e;--muted:#536971;--accent:#087c78;--paper:#fff;--bg:#f2f5f4}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.75 'Segoe UI',Arial,sans-serif}aside{position:fixed;left:0;top:0;bottom:0;width:300px;padding:24px 20px;background:#e5efec;overflow-y:auto;border-right:1px solid #ceded7}aside h2{margin:0;font-size:23px}aside p{font-size:13px;color:var(--muted)}input{width:100%;padding:12px;border:1px solid #aac3b9;border-radius:5px;font:inherit;font-size:14px}nav{margin-top:18px}nav a{display:block;padding:8px 4px;color:var(--ink);text-decoration:none;font-size:13px;line-height:1.45;border-bottom:1px solid #d2e1da}nav a:hover{color:var(--accent);background:#f6faf8}main{margin-left:300px;max-width:1300px;padding:32px 40px 70px}section{background:var(--paper);padding:34px 42px;margin:0 0 24px;border:1px solid #dfe7e3;scroll-margin-top:16px}h1{font-size:34px;line-height:1.25}h2{font-size:27px;line-height:1.35;margin-top:0;color:#075a59}h3{font-size:21px}p{margin:14px 0}li{margin:9px 0}strong{font-weight:650}a{color:#08766f}table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;font-size:14px;line-height:1.6;margin:20px 0}th,td{padding:10px 12px;border:1px solid #dce6e1;text-align:left;vertical-align:top}th{background:#edf4f0}.formula{background:#eff6f5;border-left:4px solid var(--accent);padding:15px 18px;margin:24px 0;overflow-x:auto}.formula pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:20px/1.8 'Cambria Math','Segoe UI',serif}.formula details{font-size:12px;color:var(--muted)}code{font-size:.9em;overflow-wrap:anywhere}.source{margin-top:22px;border-top:1px solid #d6e4dc;padding-top:12px;font-size:14px}summary{cursor:pointer;font-weight:600;color:#08766f}.source img{max-width:100%;height:auto;margin:15px 0;border:1px solid #dfe6e3}.muted{color:var(--muted);font-size:13px}.toolbar{display:flex;gap:12px;margin:14px 0}button{border:1px solid #b8cbc2;border-radius:4px;background:white;padding:8px 11px;color:var(--ink);cursor:pointer}section[hidden]{display:none} @media(max-width:850px){aside{position:static;width:auto;max-height:320px}main{margin-left:0;padding:15px}section{padding:24px 20px}.formula pre{font-size:17px}}@media print{aside,.toolbar,.source{display:none}main{margin:0;padding:0;max-width:none}section{border:0;padding:0 0 20px;break-before:page}body{font-size:11pt;background:white}h2{font-size:19pt}.formula pre{font-size:12pt}a{color:inherit;text-decoration:none}}
</style></head><body><aside><h2>EnzAIme study guide</h2><p>83 slides · equations · project implementation<br>12 October 2026 · works offline</p><label for="search">Find a slide or topic</label><input id="search" placeholder="Try: Ridge, pooling, legacy"><div class="toolbar"><button onclick="document.getElementById('search').value='';filterSlides()">Show all</button><button onclick="window.print()">Print</button></div><nav>${nav}</nav></aside><main>${main}</main><script>
const search=document.getElementById('search');function filterSlides(){const q=search.value.toLowerCase().trim();document.querySelectorAll('main section').forEach(s=>{s.hidden=!!q&&!s.textContent.toLowerCase().includes(q)});document.querySelectorAll('nav a').forEach(a=>{const s=document.querySelector(a.getAttribute('href'));a.hidden=s.hidden})}search.addEventListener('input',filterSlides);
</script></body></html>`;
await fs.writeFile(path.join(out,'index.html'),html);
const inputs=[
'C:/Users/Welcome/Downloads/PET_Degradation_Overview.pptx',
'backend/app/services/esm_encoder.py','backend/app/services/predictor.py','backend/app/services/recommender.py',
'backend/app/schemas/recommendation.py','frontend/src/App.jsx',
'scripts/run_controlled_ablation.py','scripts/analyze_ablation_errors.py','scripts/run_model_comparison_experiment.py',
'scripts/build_tpa_provenance_audit.py','scripts/build_confirmed_tpa_dataset.py',
'reports/results/served_model_audit/README.md','reports/results/served_model_audit/prediction_comparison.json',
'reports/results/ablation_error_analysis/pooled_metrics.csv','reports/results/ablation_error_analysis/protein_metrics.csv',
'reports/results/ablation_error_analysis/fold_metrics.csv','reports/results/protein_balance_sensitivity.json',
'reports/results/tpa_provenance_audit_summary.json','models/training_metrics.json'
];
const hashes={};for(const input of inputs){hashes[path.resolve(input)]=crypto.createHash('sha256').update(await fs.readFile(input)).digest('hex')}
await fs.writeFile(path.join(out,'source_manifest.json'),JSON.stringify({created:'2026-10-12',slides,formulas:formulaIndex,sources:hashes},null,2));
console.log(JSON.stringify({slides,formulas:formulaIndex,words:md.split(/\s+/).length,html:path.join(out,'index.html'),sourceFiles:inputs.length}));
