import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { useStore } from "./store/useStore";
import JDInput          from "./pages/JDInput";
import Dashboard        from "./pages/Dashboard";
import CandidateDetail  from "./pages/CandidateDetail";

function Nav() {
  const { modelVersion, jdId } = useStore();
  return (
    <header className="app-nav">
      <NavLink to="/" className="nav-brand">
        <span className="brand-loop">⟳</span> HireLoop
      </NavLink>
      <nav className="nav-links">
        {jdId && (
          <NavLink to="/dashboard" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            Dashboard
          </NavLink>
        )}
        {modelVersion > 0 && (
          <span className="model-badge">model v{modelVersion}</span>
        )}
      </nav>
    </header>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="app-main">
        <Routes>
          <Route path="/"                     element={<JDInput />} />
          <Route path="/dashboard"            element={<Dashboard />} />
          <Route path="/candidate/:id"        element={<CandidateDetail />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
