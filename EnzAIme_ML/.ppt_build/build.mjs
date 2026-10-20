import fs from 'node:fs/promises';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
import {applyPresentationChartFont} from 'file:///C:/Users/Welcome/.codex/plugins/cache/openai-primary-runtime/presentations/26.930.11008/skills/presentations/container_tools/artifact_tool_utils.mjs';
const E=JSON.parse(await fs.readFile('.ppt_build/evidence.json','utf8'));
const P=Presentation.create({slideSize:{width:960,height:720}});
const brown='#785644', ink='#191512', muted='#65584F', cream='#F5EADF';
const manifest=[];
function text(s,t,x=94,y=155,w=806,h=90,size=27,bold=false,color=ink,align='left'){
 const q=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});q.text=t;q.text.style={typeface:'Arial',fontSize:size,bold,color,alignment:align,verticalAlignment:'middle',autoFit:'none',wrap:'word',insets:{left:0,right:0,top:0,bottom:0}};return q;
}
function slide(title,source='',note=''){
 const s=P.slides.add();s.background.fill=cream;
 text(s,title,94,48,806,88,title.length>47?33:38,true,ink,'center');
 text(s,'Department of AI&DS',355,665,255,26,14,false,'#0000FF','center');
 text(s,String(P.slides.items.length),873,685,34,22,14,true,ink,'right');
 s.speakerNotes.textFrame.setText(`Sources: ${source}\n${note}`);
 manifest.push({slide:P.slides.items.length,title,source,note});return s;
}
function lines(s,items,y=165,size=27,gap=91){items.forEach((t,i)=>{text(s,'•',95,y+i*gap,18,58,size);text(s,t,122,y+i*gap,768,gap-12,size);});}
function callout(s,t,y=585,size=22){text(s,t,98,y,792,62,size,true,brown);}
function table(s,vals,widths,y=160,h=340,size=23){
 const t=s.tables.add({rows:vals.length,columns:vals[0].length,left:95,top:y,width:widths.reduce((a,b)=>a+b,0),height:h,columnWidths:widths,values:vals});
 for(let r=0;r<vals.length;r++)for(let c=0;c<vals[0].length;c++){let cell=t.getCell(r,c);cell.fill=r===0?brown:(r%2?'#FFF9F1':'#EEE1D4');cell.text.style={typeface:'Arial',fontSize:size,color:r===0?'#FFFFFF':ink,bold:r===0,verticalAlignment:'middle',insets:{left:10,right:10,top:7,bottom:7}};}
 const mins=vals.map((row,r)=>Math.max(...row.map((v,c)=>String(v).split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length*size*0.51/(widths[c]-20))),0)))*size*1.18+16);
 const spare=Math.max(0,h-mins.reduce((a,b)=>a+b,0));
 for(let r=0;r<vals.length;r++)t.rows[r].height=mins[r]+spare/vals.length;
 t.borders.assign({fill:'#C5B4A7',width:1,style:'solid'});return t;
}
function box(s,t,x,y,w,h=64,size=23){let q=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:'#FFF9F1',line:{fill:brown,width:1.5}});q.text=t;q.text.style={typeface:'Arial',fontSize:size,color:ink,alignment:'center',verticalAlignment:'middle',insets:{left:8,right:8,top:4,bottom:4}};return q;}
function arrow(s,x,y,w=42,h=22){s.shapes.add({geometry:'rightArrow',position:{left:x,top:y,width:w,height:h},fill:brown,line:{fill:'none',width:0}});}
function down(s,x,y,w=22,h=25){s.shapes.add({geometry:'downArrow',position:{left:x,top:y,width:w,height:h},fill:brown,line:{fill:'none',width:0}});}
async function picture(s,path,x,y,w,h){s.images.add({blob:new Uint8Array(await fs.readFile(path)),contentType:'image/png',alt:path,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
const src='data/processed/tpa_pet_ml_confirmed.csv';
const ab='reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py';
const audit='reports/results/served_model_audit/README.md';
let s;
s=slide('EnzAIme','Original title slide and project brief','Final review. Preserve team and guide identities from the supplied deck.');
text(s,'Environment-Aware AI Platform for Enzyme Recommendation and Optimization for Industrial Waste Biodegradation',108,154,774,136,30,true,ink,'center');
text(s,'Current research: TPA/PET activity prediction',105,307,780,48,26,true,brown,'center');
text(s,'MEMBERS:  Ramkumar R   ·   Sukil Raj M S\nGUIDE:  Mr. G. Kirubakaran B.E., M.E.',126,383,748,95,25);
text(s,'Department of Artificial Intelligence and Data Science\nMepco Schlenk Engineering College',126,508,748,75,23,false,ink,'center');
text(s,'Final-year project review',126,602,748,32,22,false,brown,'center');

s=slide('Motivation and current scope','Original slides 2–7; '+src);
lines(s,['The original proposal addresses enzyme selection under industrial wastewater conditions.','The current research focuses on PET degradation assays with recorded TPA concentrations.','Temperature, pH and reaction duration describe the available assay environment.','Dyes, PU, phenolics and other waste streams remain expansion targets.'],155,27,104);

s=slide('Aim and research objectives',src+'; scripts/');
lines(s,['Build a traceable dataset linking protein sequences, assay conditions and measured TPA.','Compare environmental features with frozen ESM-2 protein representations.','Evaluate generalization to held-out proteins using grouped cross-validation.','Support a recommendation prototype and identify the evidence needed for future optimization.'],156,27,106);

s=slide('Current work and long-term proposal',audit+'; '+ab);
table(s,[['Stage','Present scope'],['Confirmed research','221 records, 25 proteins, frozen ESM-2, controlled Ridge experiments'],['Application prototype','React/Vite and FastAPI using a separate legacy model artifact'],['Future research','Robust fitness oracle, mutation design, structural and experimental validation']],[230,570],166,370,25);
callout(s,'The confirmed research experiment does not validate the separately served legacy model.');

s=slide('Literature survey: evolution and structure','https://github.com/HySonLab/Directed_Evolution; https://ieeexplore.ieee.org/document/10443319/','Hong title corrected to Artificial Intelligence. Bibliographic details retained from the source deck; full paper access was limited.');
table(s,[['Study','Contribution','Gap investigated here'],['Tran & Hy (2025)\nProtein Design by Directed Evolution Guided by Large Language Models','Language-model-guided candidate generation and a learned fitness oracle','Assay conditions and PET/TPA activity require a separate, validated dataset'],['Hong et al. (2025)\nProtein Structure Prediction Using a New Optimization-Based Evolutionary and Explainable Artificial Intelligence Approach','Evolutionary optimization and explainability for structure prediction','Structure prediction alone does not establish condition-specific enzyme activity']],[280,250,270],159,445,20);

s=slide('Literature survey: protein representations','https://doi.org/10.1126/science.ade2574; https://doi.org/10.1073/pnas.2016239118');
table(s,[['Study','Contribution','Gap investigated here'],['Lin et al. (2023)\nEvolutionary-scale prediction of atomic-level protein structure with a language model','Large protein language models support structural prediction','Test whether frozen representations support TPA prediction with assay conditions'],['Rives et al. (2021)\nBiological structure and function emerge from scaling unsupervised learning to 250 million protein sequences','Sequence learning captures biological structure and function','Representation quality does not guarantee activity prediction on 25 proteins']],[280,250,270],159,425,21);
callout(s,'EnzAIme tests a specific application of these ideas. It does not claim to solve every gap.',593,21);

s=slide('Research gap and question','Project brief; '+ab);
text(s,'Protein representation + environmental conditions + recorded activity + retained provenance',105,175,782,111,31,true,brown,'center');
text(s,'Can protein sequence representations and environmental conditions jointly support reliable enzyme activity prediction under plastic-degradation conditions?',108,335,778,158,31,true,ink,'center');
callout(s,'The current experiments test this question under limited protein coverage.');

s=slide('Dataset sources and intended roles','master_dataset.csv; reports/results/tpa_provenance_audit_summary.json; reports/results/fireprotdb_analysis.json');
table(s,[['Source','Role in EnzAIme'],['PAZy','Plastic-active enzymes and recorded PET/TPA assay evidence'],['UniProt','Protein sequences and biological metadata'],['BRENDA','Enzyme-property and condition context'],['FireProtDB','Mutation/stability evidence for future analysis'],['PDB','Structural information for future validation'],['Wastewater datasets','Environmental scenarios and context, not activity labels']],[220,580],151,435,23);
callout(s,'Confirmed labels trace to PAZy assay records. Other sources do not imply complete label coverage.',594,21);

s=slide('Dataset construction and provenance','master_dataset.csv; '+src+'; reports/results/tpa_provenance_audit_summary.json');
const stages=[['Biological sources','462 master records','7,195 embedded assays'],['TPA/PET extraction','227 candidate records','Provenance review'],['Exclude 6 ambiguous','221 confirmed records','25 protein groups']];
stages.forEach((row,r)=>row.forEach((t,c)=>{box(s,t,104+c*277,170+r*125,244,72,23);if(c<2)arrow(s,352+c*277,194+r*125,25,20);}));
callout(s,'Labels derive from recorded experimental measurements, including digitized source values. Duration is normalized to hours.',561,23);

s=slide('Confirmed dataset profile',src+'; reports/results/tpa_confirmed_dataset_summary.json');
table(s,[['Property','Verified value'],['Activity observations / proteins','221 / 25'],['Target','TPA concentration, standardized to µM'],['Temperature / pH','25–80 °C / 7–9'],['Duration','0–672 hours'],['Target range / median','0.3–47,000 µM / 194.8 µM'],['Current inputs','Sequence embedding, temperature, pH, duration']],[330,470],153,434,24);
callout(s,'Target field: target_value_standardized. Concentration is an assay endpoint, not a universal fitness score.',598,21);

s=slide('Activity provenance audit','reports/results/tpa_confirmed_dataset_summary.json; reports/results/tpa_ambiguous_review.md');
table(s,[['Audit finding','Confirmed dataset'],['Ambiguous records excluded','6 records, retained separately'],['Repeated protein-condition groups','48'],['Exact duplicate groups / rows involved','4 groups / 9 rows'],['Zero-duration observations','8'],['Sequence identity audit','25 unique sequences, no exact cross-protein duplicates']],[475,325],163,380,24);
callout(s,'Repeated conditions and duplicate patterns were audited. They were not automatically discarded.',571,24);

s=slide('Protein imbalance and assay variability','reports/results/repeated_condition_variability.json; '+src);
table(s,[['Protein','Records'],...E.counts.slice(0,3).map(x=>[x.protein_name,String(x.records)]),['Remaining 22 proteins','113']],[250,150],168,286,25);
text(s,'HiC contributes 75 of 221 observations (33.9%).',537,170,350,100,28,true,brown);
text(s,'47 of 48 repeated-condition groups have different targets. All 48 have recorded metadata differences.',537,300,350,152,25);
callout(s,'Matching protein, pH, temperature and duration does not establish identical experimental protocols.',532,25);

s=slide('Feature eligibility and leakage audit','reports/results/feature_eligibility_audit.csv');
table(s,[['Classification','Features'],['SAFE','1'],['SAFE_WITH_CAUTION','14'],['LEAKAGE_RISK','24'],['NOT_RECOMMENDED','4'],['FUTURE_FEATURE','5']],[360,160],154,334,23);
text(s,'48 candidate features audited',643,174,250,95,28,true,brown);
text(s,'Protein ID is for grouping. Source IDs, outcomes and protocol-rich metadata are excluded.',643,300,250,170,24);
callout(s,'Salinity, COD, BOD and pollutant type lack confirmed-label coverage. EC numbers are empty in this cohort.',525,24);

s=slide('Controlled feature configurations','reports/results/research_feature_matrix_summary.json');
table(s,[['Configuration','Inputs','Raw dimensions'],['A','Temperature, pH, duration','3'],['B','Frozen ESM-2 embedding','1,280'],['C','ESM-2 + environment','1,283'],['D (rejected)','ESM-2 + environment + material + substrate','Not evaluated']],[200,425,175],165,332,23);
callout(s,'Material descriptions are source/protocol-specific. Substrate is PET in all 221 rows, so it adds no variation.',540,25);

s=slide('What model are we using?',ab+'; backend/app/services/esm_encoder.py');
text(s,'Frozen ESM-2 + Ridge regression',103,164,790,78,38,true,brown,'center');
table(s,[['Component','Current controlled baseline'],['Feature extractor','facebook/esm2_t33_650M_UR50D'],['Protein representation','1,280-dimensional vector, no fine-tuning'],['Supervised estimator','Ridge regression, α = 10'],['Dimensionality reduction','10 PCA components for B and C'],['Target / validation','log1p target / 5-fold GroupKFold by protein']],[285,515],274,316,23);

s=slide('Frozen ESM-2 feature extraction','backend/app/services/esm_encoder.py; data/embeddings/index.json; reports/results/research_feature_matrix_summary.json','Current implementation pools all attention-mask tokens, including special tokens; it truncates at 1024 tokens. Existing vectors reused, no regeneration.');
box(s,'Protein sequence',287,148,415,52);down(s,484,204);
box(s,'Tokenizer',287,235,415,52);down(s,484,290);
box(s,'Frozen ESM-2 Transformer\n33 layers, 650M parameters',247,321,495,72);down(s,484,397);
box(s,'Attention-mask mean pooling',287,428,415,52);down(s,484,483);
box(s,'1,280-dimensional embedding',287,514,415,52);
callout(s,'25/25 confirmed proteins have finite vectors. Current pooling includes special tokens.',587,22);

s=slide('Current research prediction pipeline',ab);
box(s,'ESM-2 vector\n1,280 features',110,164,305,75);box(s,'Temperature, pH, duration\n3 features',555,164,325,75);
down(s,250,245);box(s,'Train-only scaling + PCA\n10 components',110,286,305,76);down(s,708,245,22,30);
arrow(s,425,314,111,22);box(s,'Concatenate\n13 model inputs',555,286,325,76);
down(s,708,369);box(s,'Train-only final scaling + Ridge',386,421,494,58);down(s,627,486);box(s,'TPA prediction after expm1',386,521,494,48,23);
callout(s,'Configuration C shown. Raw feature fusion is 1,283-dimensional before PCA reduction.',586,23);

s=slide('Representation and feature equations','backend/app/services/esm_encoder.py; '+ab,'m_i is 1 for attended tokens. This corrects the brief’s residue-only pooling description to match the implementation.');
text(s,'Mean pooling',104,162,770,38,27,true,brown);
text(s,'h = ( Σᵢ mᵢ hᵢ ) / ( Σᵢ mᵢ )',115,214,750,60,35,false,ink,'center');
text(s,'hᵢ: token representation     mᵢ: attention-mask indicator',106,291,785,47,23);
text(s,'Raw feature fusion',104,380,770,40,27,true,brown);
text(s,'x = [ z_ESM ; T ; pH ; d ]     dim(x) = 1,283',110,439,775,66,31,false,ink,'center');
callout(s,'z_ESM has 1,280 features. T is temperature and d is duration in hours.',567,24);

s=slide('Ridge training and prediction',ab,'Ridge fits an intercept by default. The objective uses transformed training targets. log1p itself has no fitted parameters, but is applied within the fold training flow.');
text(s,"Target transform:     y′ = ln(1 + y)",108,173,780,55,32);
text(s,'Minimize over w and b:',108,270,780,40,24,true,brown);
text(s,'‖y′ − Xw − b1‖₂² + α‖w‖₂²',108,324,780,65,34,false,ink,'center');
text(s,'α = 10. The fitted intercept b is unpenalized.',108,401,780,52,25);
text(s,'Prediction:     ŷ = exp(ŷ′) − 1',108,490,780,61,32);
callout(s,'Evaluation returns to the original µM scale.',591,24);

s=slide('Evaluation metrics',ab);
text(s,'MAE = (1/n) Σᵢ |yᵢ − ŷᵢ|',111,162,772,54,31);
text(s,'RMSE = √[(1/n) Σᵢ (yᵢ − ŷᵢ)²]',111,251,772,54,31);
text(s,'R² = 1 − Σᵢ(yᵢ − ŷᵢ)² / Σᵢ(yᵢ − ȳ)²',111,340,772,62,29);
text(s,'Spearman ρ = corr(rank(y), rank(ŷ))',111,438,772,58,29);
callout(s,'MAE/RMSE measure error in µM. Negative R² means worse squared error than the held-out mean baseline.',545,24);

s=slide('Protein-grouped cross-validation',ab);
text(s,'All records for a protein stay in one fold.',109,145,775,57,30,true,brown,'center');
table(s,[['Fold','Test observations','Test proteins'],...E.folds.map(x=>[String(x.fold),String(x.test_records),String(x.test_proteins)])],[180,335,285],230,275,23);
callout(s,'Train proteins ≠ test proteins. Fit PCA/scalers on training data only, then transform the held-out fold.',541,25);

s=slide('Controlled ablation results',ab,'Arithmetic means of fold metrics. B Spearman excludes undefined fold 1 and uses four defined folds; all other displayed means use five folds. These are not pooled OOF metrics.');
table(s,[['Features','MAE (µM)','RMSE (µM)','R²','Spearman'],...Object.entries(E.metrics).map(([k,v])=>[({A:'A  Environment',B:'B  ESM-2',C:'C  Combined'})[k],v.mae_um.toFixed(2),v.rmse_um.toFixed(2),v.r2.toFixed(2),v.spearman.toFixed(3)])],[220,145,155,135,145],188,275,22);
text(s,'Mean fold metrics, same grouped splits and Ridge α = 10.',105,492,785,46,24);
callout(s,'B Spearman averages 4 defined folds. Fold 1 is undefined because its predictions are constant.',564,22);

s=slide('Ablation: absolute prediction error',ab,'Editable chart generated from actual CSV fold means. No synthetic metric values.');
const chart=s.charts.add('bar',{position:{left:110,top:161,width:773,height:390},categories:['A Environment','B ESM-2','C Combined'],series:[{name:'MAE',values:Object.values(E.metrics).map(x=>Number(x.mae_um.toFixed(2))),fill:'#92725F'},{name:'RMSE',values:Object.values(E.metrics).map(x=>Number(x.rmse_um.toFixed(2))),fill:'#344E54'}],barOptions:{direction:'column',grouping:'clustered',gapWidth:130},hasLegend:true,legend:{position:'bottom'},xAxis:{textStyle:{fontSize:20}},yAxis:{title:'Error (µM)',numberFormatCode:'0',minimumScale:0,textStyle:{fontSize:19}},dataLabels:{showValue:true,numberFormatCode:'0',position:'outEnd',textStyle:{fontSize:18}},chartFill:'#FFF9F1',plotAreaFill:'#FFF9F1'});applyPresentationChartFont(chart,{fontFamily:'Arial'});
callout(s,'Combined features reduce error relative to ESM-2 alone, but do not outperform environment-only here.',580,24);

s=slide('What the current results tell us',ab);
lines(s,['Environment-only shows positive mean ranking signal (Spearman 0.313).','ESM-2 alone generalizes poorly in this small dataset. Adding conditions helps relative to ESM-2 alone.','Negative mean R² and large fold differences limit claims about absolute prediction.','These findings concern this dataset and setup. They do not establish that protein language models are ineffective.'],159,26,110);

s=slide('Completed fold-level error analysis','reports/results/ablation_error_analysis/actual_vs_predicted.png; reports/results/ablation_error_analysis/ablation_error_analysis_report.md');
await picture(s,'reports/results/ablation_error_analysis/actual_vs_predicted.png',97,150,799,396);
text(s,'Research experiment output: saved out-of-fold prediction plots.',102,554,790,36,20,false,muted,'center');
callout(s,'Per-fold and per-protein diagnostics are complete. Interpretation and model refinement continue.',596,22);

s=slide('Error analysis: two major findings','reports/results/ablation_error_analysis/targeted_audit/targeted_audit_report.md','The targeted report contains a conflicting B fold-1 constant value. That constant is omitted. Controlled metrics are taken directly from the CSV.');
text(s,'PHL-7 in fold 2',110,162,770,40,29,true,brown);
text(s,'Observed TPA reaches 47,000 µM. The fold’s training targets reach only about 6,860 µM. The retained provenance supports 47 mM converted to µM.',110,221,770,135,27);
text(s,'Protein 606 in fold 3',110,398,770,40,29,true,brown);
text(s,'Overprediction for this protein contributes 99.3% of B’s and 98.0% of C’s fold-3 squared error.',110,458,770,100,27);
callout(s,'Large values and repeated conditions require source review, not automatic removal.',584,23);

s=slide('Additional research already completed','reports/results/model_comparison_results.json; reports/results/protein_balance_sensitivity.md; reports/results/repeated_condition_variability.json','These follow-up experiments differ from the fixed A/B/C ablation. No production model selection or deployment follows from them.');
lines(s,['Model comparison reports evaluate Ridge, ElasticNet, Random Forest and Gradient Boosting.','A separate balance analysis samples at most 5 records per protein: 82 records across all 25 proteins.','Repeated-condition analysis records protocol/metadata differences across all 48 repeated groups.','These are exploratory follow-ups. Final model selection and an independently validated serving artifact remain open.'],156,26,109);

s=slide('Software architecture','backend/app/api/routes.py; backend/app/services/; frontend/src/App.jsx; '+audit);
box(s,'User',115,163,151,62);arrow(s,277,184,40);box(s,'React / Vite',330,163,254,62);arrow(s,596,184,40);box(s,'FastAPI',651,163,235,62);
down(s,756,237);box(s,'Predict / recommend services',499,280,387,67);down(s,678,355);
box(s,'ESM-2 + saved PCA/scaler/Ridge\nLegacy 227-row candidate evidence',384,399,502,91);
box(s,'Research scripts\nConfirmed 221-row dataset\nA/B/C evaluation reports',112,363,230,175,23);
callout(s,'Application serving and confirmed-data experiments are distinct paths. Production use is future work.',572,24);

s=slide('Served model: lineage and reproducibility',audit+'; models/model_config.json');
lines(s,['Saved PCA/scaler metadata points to 227 legacy observations, including the 6 ambiguous source rows.','Exact final Ridge training rows, saved CV membership and artifact-to-run linkage remain unresolved.','The recommendation source is the legacy CSV. Its evidence counts are not confirmed-record counts.','A one-input check matched across scikit-learn 1.9.1 and 1.6.1. This does not establish general compatibility or scientific validity.'],155,25,112);

s=slide('Actual saved API output','reports/results/served_model_audit/live_api_prediction.json; reports/results/served_model_audit/prediction_comparison.json','Saved API output from the 2026-09-28 audit, not a newly run inference or screenshot.');
table(s,[['Input','Value'],['Protein','IsPETase'],['Temperature / pH','40 °C / 8.0'],['Duration / substrate','48 hours / PET'],['Returned TPA prediction','23.14270943 µM']],[330,470],166,330,27);
callout(s,'Actual system output from the legacy model. This is a prediction example, not a measured assay result.',546,25);

for(const [title,img,caption] of [
 ['Prototype interface: home','screenshot_42_0.png','Archived system screenshot from the supplied deck. Initial prototype interface.'],
 ['Prototype interface: recommendation','screenshot_44_0.png','Archived rule-based output. Suitability percentages are not learned activity predictions.'],
 ['Prototype interface: enzyme details','screenshot_47_0.png','Archived system screenshot. Enzyme metadata and preliminary mutation controls.']]){
 s=slide(title,'Original PPT embedded screenshot, preserved without fabrication','These images document the older prototype and do not represent the current React interface or confirmed-model inference.');
 await picture(s,'.ppt_build/'+img,98,155,795,408);text(s,caption,102,582,790,63,23,true,brown);
}

s=slide('Initial rule-based baseline','Original slide 31','Historical prototype documentation. The formula is preserved for context, not claimed as the current learned predictor.');
text(s,'S = 0.40 P + 0.25 H + 0.25 T + 0.10 Sₐ',101,180,795,80,31,true,ink,'center');
table(s,[['Compatibility term','Weight'],['Pollutant (P)','0.40'],['pH (H)','0.25'],['Temperature (T)','0.25'],['Salinity (Sₐ)','0.10']],[560,240],289,236,24);
callout(s,'This transparent score was an initial prototype baseline. It is separate from the learned TPA predictor.',566,24);

s=slide('Preliminary mutation prioritization','Original slide 32; reports/results/fireprotdb_analysis.json','Current EnzAIme_ML routes do not expose a mutation endpoint. Historical implementation claims are not carried into the present ML application.');
text(s,'Historical prototype score',110,159,775,44,28,true,brown);
text(s,'S_mut = 0.7 × stability proxy + 0.3 × fitness proxy',110,234,775,83,29,false,ink,'center');
lines(s,['Physicochemical proxies rank computational mutation hypotheses.','Current FireProtDB matching provides insufficient mutation/ΔΔG evidence for this 25-protein model.'],363,26,100);
callout(s,'Mutation candidates require experimental validation. No validated mutation predictor is established.',578,25);

s=slide('Current implementation status',src+'; reports/results/; backend/app/; frontend/src/');
table(s,[['Status','Evidence-backed scope'],['Completed','Master integration, TPA extraction, provenance/ambiguity review, duration normalization'],['Completed','ESM-2 vectors, leakage audit, feature matrices, grouped A/B/C validation'],['Completed','Fold diagnostics, targeted audits, model comparison and balance sensitivity'],['Prototype available','FastAPI backend and React/Vite frontend'],['In progress / open','Model refinement, explainability, uncertainty and final model selection'],['Future','Validated mutation design, structures, docking, wet-lab study']],[200,600],153,456,22);

s=slide('Codebase and verification evidence','backend/app/; frontend/src/; scripts/; tests/test_legacy_evidence_integration.py; '+audit,'No existing application tests were rerun for this presentation-only edit. The old 54-test assertion and clean-install claim are not supported for this repository.');
table(s,[['Location','Role'],['backend/app/','FastAPI routes, ESM encoder, prediction and ranking'],['frontend/src/','React interface and research/legacy evidence labels'],['scripts/','Dataset audits and reproducible research experiments'],['data/ and models/','Confirmed/legacy datasets, stored embeddings and serving artifacts'],['reports/results/','Ablation, diagnostics and lineage evidence']],[280,520],158,350,23);
callout(s,'Verification includes embedding finiteness, protein split checks and a saved API compatibility probe. Software checks do not establish predictive validity.',545,23);

s=slide('Current limitations',src+'; '+ab+'; '+audit);
lines(s,['Only 25 protein groups and 221 observations, with imbalanced counts and a wide target range.','Available conditions are temperature, pH and duration. Protocol differences remain partly unmodeled.','Negative R², high fold variability and repeated-condition differences limit generalization.','Mutation evidence is insufficient. No wet-lab validation or industrial deployment is established.','Legacy serving lineage and environment reproducibility need further resolution.'],150,25,96);

s=slide('Long-term EnzAIme architecture','Original proposed architecture and user brief','PROPOSED / FUTURE ARCHITECTURE. This diagram is a roadmap, not a claim that its modules are trained.');
text(s,'PROPOSED / FUTURE ARCHITECTURE',108,139,780,38,24,true,brown,'center');
box(s,'Wastewater conditions\nEnvironmental encoder',113,198,330,69,23);box(s,'Protein sequence\nESM-2 encoder',553,198,330,69,23);
down(s,266,276);down(s,706,276);box(s,'Multimodal fusion + condition-aware fitness oracle',178,319,650,62,23);down(s,492,389);
box(s,'Candidate generation + mutation prioritization',178,430,650,62,23);down(s,492,500);
box(s,'Iterative directed evolution / beam search',178,537,650,53,23);
text(s,'Structural validation followed by experimental validation',110,609,778,38,23,true,brown,'center');

s=slide('Future masking and evolution strategy','Original slides 14–22; https://github.com/HySonLab/Directed_Evolution','Proposal adapted from literature. No current EnzAIme condition-aware neural oracle has been established as trained.');
lines(s,['Random masking explores sequence positions. An importance strategy would prioritize candidate hotspots.','A future language-model generation step proposes substitutions. A validated condition-aware oracle would rank them.','Beam search would retain a small set of candidates over successive rounds.','Structural assessment and laboratory measurements must test the proposed improvements.'],157,26,108);

s=slide('Future work in research order','Project brief updated against existing reports');
table(s,[['Stage','Next work'],['1. Resolve evidence','Extend error analysis, source uncertainty and served-artifact lineage'],['2. Improve data','Balance observations, expand proteins and industrial condition coverage'],['3. Evaluate models','Representation/hyperparameter studies, uncertainty and explainability'],['4. Rank candidates','Validate condition-aware ranking before mutation prioritization'],['5. Validate design','Structural analysis, docking and experimental testing'],['6. Report findings','Reproducible experiments and a research paper']],[250,550],157,423,23);

s=slide('Outputs, feasibility and intended impact','Project brief; repository artifacts');
table(s,[['Current output','Future output'],['Confirmed TPA/PET dataset and retained provenance','Broader industrial-condition activity dataset'],['Verified frozen ESM-2 vectors and ML feature matrices','Robust condition-aware fitness oracle'],['Controlled experiments and diagnostic reports','Validated candidate and mutation ranking'],['Recommendation and prediction prototype','Structural and experimental validation']],[400,400],173,337,23);
callout(s,'Open-source tools and reused embeddings support feasibility. Environmental benefit requires experimental and deployment evidence.',554,23);

s=slide('Conclusion',src+'; '+ab+'; reports/results/ablation_error_analysis/');
lines(s,['EnzAIme establishes a provenance-aware framework for condition-aware enzyme research.','The current work provides confirmed PET/TPA labels, frozen ESM-2 features and protein-grouped evaluation.','Controlled ablation shows environmental ranking signal alongside substantial prediction and generalization limits.','Further data, model refinement and experimental validation are necessary before industrial use.'],155,27,110);

s=slide('References and research evidence','Bibliographic references and local project evidence');
text(s,'Tran & Hy (2025). Protein Design by Directed Evolution Guided by Large Language Models. IEEE TEVC. DOI: 10.1109/TEVC.2024.3439690',103,149,790,84,22);
text(s,'Hong et al. (2025). Protein Structure Prediction Using a New Optimization-Based Evolutionary and Explainable Artificial Intelligence Approach. IEEE TEVC. IEEE document 10443319.',103,248,790,102,22);
text(s,'Lin et al. (2023). Evolutionary-scale prediction of atomic-level protein structure with a language model. Science. DOI: 10.1126/science.ade2574',103,364,790,84,22);
text(s,'Rives et al. (2021). Biological structure and function emerge from scaling unsupervised learning to 250 million protein sequences. PNAS. DOI: 10.1073/pnas.2016239118',103,460,790,100,22);
text(s,'Project evidence: confirmed dataset, controlled ablation, diagnostic reports and served-model audit. Exact paths appear in slide notes.',103,580,790,57,20,false,brown);

s=slide('Thank you','Original closing slide');
text(s,'Questions and discussion',116,282,756,80,44,true,ink,'center');
text(s,'EnzAIme\nEnvironment-aware enzyme research',116,419,756,95,29,false,brown,'center');

if(P.slides.items.length!==45)throw new Error('Expected 45 slides, got '+P.slides.items.length);
await fs.writeFile('.ppt_build/slide_manifest.json',JSON.stringify(manifest,null,2));
await (await PresentationFile.exportPptx(P)).save('.ppt_build/content.pptx');
console.log('Authored',P.slides.items.length,'editable slides');




