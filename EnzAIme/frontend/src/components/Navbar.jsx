import { NavLink } from "react-router-dom";
import "./Navbar.css";

const links = [
  { to: "/", label: "Overview", end: true },
  { to: "/recommend", label: "Recommend" },
  { to: "/about", label: "Methodology" },
];

export default function Navbar() {
  return (
    <header className="nav">
      <div className="container nav-inner">
        <NavLink to="/" className="nav-brand" end>
          <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="6" fill="#D9A441" />
            <path d="M9 22c0-7 3-11 7-11s7 4 7 11" stroke="#123C39" strokeWidth="2.4" fill="none" strokeLinecap="round" />
            <circle cx="16" cy="11" r="2.4" fill="#123C39" />
          </svg>
          <span className="nav-wordmark">ENZAIme</span>
        </NavLink>
        <nav className="nav-links">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              {l.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
