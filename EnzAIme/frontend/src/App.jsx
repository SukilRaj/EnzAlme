import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import Landing from "./pages/Landing";
import Recommend from "./pages/Recommend";
import Results from "./pages/Results";
import EnzymeDetail from "./pages/EnzymeDetail";
import Mutations from "./pages/Mutations";
import Simulate from "./pages/Simulate";
import About from "./pages/About";

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/recommend" element={<Recommend />} />
          <Route path="/results" element={<Results />} />
          <Route path="/enzyme/:enzymeId" element={<EnzymeDetail />} />
          <Route path="/enzyme/:enzymeId/mutations" element={<Mutations />} />
          <Route path="/simulate/:enzymeId" element={<Simulate />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

function NotFound() {
  return (
    <div className="container" style={{ padding: "90px 28px", textAlign: "center" }}>
      <h1>Page not found</h1>
      <p>That route doesn't exist in ENZAIme.</p>
    </div>
  );
}
