import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../store/useStore";
import { WhyPanel } from "../components/WhyPanel";

export default function ComparePage() {
  const navigate    = useNavigate();
  const { candidates } = useStore();
  const [selectedIds, setSelected] = useState<string[]>([]);

  const toggle = (id: string) => {
    setSelected(prev =>
      prev.includes(id)
        ? prev.filter(x => x !== id)
        : prev.length < 2 ? [...prev, id] : [prev[1], id]
    );
  };

  const pair = selectedIds.map(id => candidates.find(c => c.candidate_id === id)).filter(Boolean) as typeof candidates;

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <button className="back-link" onClick={() => navigate("/dashboard")}>← Back</button>
      <h2 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: 4 }}>Compare candidates</h2>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 20 }}>
        Select 2 candidates to compare side-by-side.
      </p>

      {/* Picker */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 24 }}>
        {candidates.map(c => {
          const sel = selectedIds.includes(c.candidate_id);
          return (
            <button
              key={c.candidate_id}
              onClick={() => toggle(c.candidate_id)}
              className="btn btn-secondary btn-sm"
              style={{
                borderColor: sel ? "var(--indigo-500)" : undefined,
                background:  sel ? "var(--indigo-50)"  : undefined,
                color:       sel ? "var(--indigo-700)"  : undefined,
              }}
            >
              {sel ? "✓ " : ""} #{c.rank} {c.name}
            </button>
          );
        })}
      </div>

      {pair.length === 2 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {pair.map(c => {
            const pct  = Math.round((c.fit_score ?? 0) * 100);
            const tier = pct >= 70 ? "high" : pct >= 45 ? "mid" : "low";
            return (
              <div key={c.candidate_id} className="card card-p">
                {/* Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 15 }}>{c.name}</div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Rank #{c.rank}</div>
                  </div>
                  <div className={`hero-score-num ${tier}`} style={{ fontSize: "1.6rem" }}>
                    {pct}%
                  </div>
                </div>

                {/* Score bar */}
                <div className="hero-bar" style={{ marginBottom: 16 }}>
                  <div className="hero-bar-fill" style={{
                    width: `${pct}%`,
                    background: tier === "high" ? "var(--green-500)" : tier === "mid" ? "var(--amber-500)" : "var(--red-500)"
                  }} />
                </div>

                <WhyPanel features={c.features} name={c.name} />

                {c.decision && (
                  <div style={{ marginTop: 14 }}>
                    <span className={`badge ${c.decision === "approve" ? "badge-green" : "badge-red"}`}>
                      {c.decision === "approve" ? "✓ Approved" : "✕ Rejected"}
                    </span>
                  </div>
                )}

                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginTop: 14, width: "100%" }}
                  onClick={() => navigate(`/candidate/${c.candidate_id}`)}
                >
                  Open full profile →
                </button>
              </div>
            );
          })}
        </div>
      )}

      {pair.length < 2 && (
        <div style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "3rem", border: "2px dashed var(--border)", borderRadius: "var(--r-lg)" }}>
          Select {2 - pair.length} more candidate{2 - pair.length > 1 ? "s" : ""} to compare
        </div>
      )}
    </div>
  );
}
