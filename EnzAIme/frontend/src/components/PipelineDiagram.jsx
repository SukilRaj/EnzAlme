import "./PipelineDiagram.css";

/**
 * Hero illustration: a schematic of the actual recommendation pipeline
 * (input variables -> compatibility engine -> ranked candidates), styled
 * like an annotated lab notebook diagram rather than decorative art.
 */
export default function PipelineDiagram() {
  return (
    <div className="pipeline-diagram" aria-hidden="true">
      <svg viewBox="0 0 380 420" width="100%" role="img">
        {/* connecting spine */}
        <line x1="190" y1="46" x2="190" y2="374" stroke="var(--line)" strokeWidth="2" strokeDasharray="1 7" strokeLinecap="round" />

        {/* Node 1: environment input */}
        <g>
          <rect x="40" y="14" width="300" height="64" rx="6" fill="var(--paper-raised)" stroke="var(--line)" />
          <text x="58" y="36" fontFamily="var(--font-mono)" fontSize="10" fill="var(--slate-2)">INPUT</text>
          <text x="58" y="58" fontFamily="var(--font-mono)" fontSize="13" fill="var(--ink-teal)">PET · pH 8.0 · 35°C · 0.5%</text>
        </g>

        {/* Node 2: compatibility engine */}
        <g>
          <rect x="70" y="128" width="240" height="72" rx="6" fill="var(--ink-teal)" />
          <text x="88" y="154" fontFamily="var(--font-mono)" fontSize="10" fill="var(--amber)">COMPATIBILITY ENGINE</text>
          <text x="88" y="176" fontFamily="var(--font-body)" fontSize="12.5" fill="var(--paper)">pollutant · pH · temp · salinity</text>
          <text x="88" y="192" fontFamily="var(--font-body)" fontSize="12.5" fill="var(--paper)">weighted suitability score</text>
        </g>

        {/* Node 3: ranked results */}
        <g>
          <rect x="40" y="246" width="300" height="94" rx="6" fill="var(--paper-raised)" stroke="var(--line)" />
          <text x="58" y="266" fontFamily="var(--font-mono)" fontSize="10" fill="var(--slate-2)">RANKED CANDIDATES</text>
          {[
            { name: "IsPETase", pct: 98, y: 286 },
            { name: "MHETase", pct: 98, y: 306 },
            { name: "BurPL", pct: 86, y: 326 },
          ].map((r) => (
            <g key={r.name}>
              <text x="58" y={r.y} fontFamily="var(--font-mono)" fontSize="12" fill="var(--ink-teal)">{r.name}</text>
              <rect x="200" y={r.y - 10} width="110" height="6" rx="3" fill="var(--line)" />
              <rect x="200" y={r.y - 10} width={110 * (r.pct / 100)} height="6" rx="3" fill="var(--moss)" />
              <text x="320" y={r.y} fontFamily="var(--font-mono)" fontSize="11" fill="var(--slate)" textAnchor="end">{r.pct}%</text>
            </g>
          ))}
        </g>

        {/* Node 4: mutation module */}
        <g>
          <rect x="70" y="360" width="240" height="46" rx="6" fill="var(--paper-raised)" stroke="var(--amber)" strokeDasharray="4 3" />
          <text x="88" y="380" fontFamily="var(--font-mono)" fontSize="10" fill="var(--amber-deep)">MUTATION MODULE</text>
          <text x="88" y="396" fontFamily="var(--font-mono)" fontSize="11.5" fill="var(--ink-teal)">P217T · K259R · P174T …</text>
        </g>

        {/* arrows */}
        {[112, 228, 344].map((y) => (
          <polygon key={y} points={`184,${y} 196,${y} 190,${y + 10}`} fill="var(--amber)" />
        ))}
      </svg>
    </div>
  );
}
