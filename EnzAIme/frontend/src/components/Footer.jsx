export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <p className="footer-note">
          ENZAIme is an in-silico decision-support tool. Suitability scores are project-defined
          compatibility estimates, not experimentally measured degradation efficiency. Mutation
          predictions require experimental validation.
        </p>
        <p className="footer-meta mono">MVP build — final-year project review</p>
      </div>
    </footer>
  );
}
