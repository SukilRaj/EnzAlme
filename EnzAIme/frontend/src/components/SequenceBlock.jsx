/** Renders a protein sequence in chunked, mono-spaced blocks (10 residues
 * per group, 6 groups per line) — the classic sequence-viewer convention. */
export default function SequenceBlock({ sequence }) {
  if (!sequence) return null;
  const groups = sequence.match(/.{1,10}/g) || [];
  const lines = [];
  for (let i = 0; i < groups.length; i += 6) {
    lines.push(groups.slice(i, i + 6));
  }
  return (
    <div className="sequence-block">
      {lines.map((line, li) => (
        <div key={li}>
          <span className="residue-index">{String(li * 60 + 1).padStart(4, " ")}</span>{"  "}
          {line.join(" ")}
        </div>
      ))}
    </div>
  );
}
