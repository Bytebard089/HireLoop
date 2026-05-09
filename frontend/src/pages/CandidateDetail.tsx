import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useStore, getPersistedJdId } from "../store/useStore";
import { WhyPanel } from "../components/WhyPanel";
import { AdaptiveQs } from "../components/AdaptiveQs";
import { FeedbackButtons } from "../components/FeedbackButtons";
import { listCandidates } from "../api/client";

export default function CandidateDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"why" | "questions">("why");
  const [recovering, setRecovering] = useState(false);

  const { candidates, questions, jdId, setCandidates, setJD } = useStore();

  // ── Recover state on page refresh ────────────────────────────────────────
  useEffect(() => {
    if (jdId && candidates.length > 0) return; // already loaded
    const savedJdId = jdId || getPersistedJdId();
    if (!savedJdId) return;

    setRecovering(true);
    if (!jdId) {
      setJD(savedJdId, "", { skills: [], exp_years: 0, level: "", keywords: [] });
    }

    listCandidates(savedJdId)
      .then((res) => {
        if (res.candidates?.length) {
          setCandidates(res.candidates, questions);
        }
      })
      .catch((e) => console.error("Failed to recover candidates:", e))
      .finally(() => setRecovering(false));
  }, []);

  const candidate = candidates.find((c) => c.candidate_id === id);

  if (recovering) {
    return (
      <div className="page-empty">
        <p>Loading candidate…</p>
      </div>
    );
  }

  if (!candidate || !jdId) {
    return (
      <div className="page-empty">
        <p>Candidate not found. <button className="btn-link" onClick={() => navigate("/dashboard")}>← Back</button></p>
      </div>
    );
  }

  // Pass undefined instead of empty array so AdaptiveQs always fetches when no cache
  const cachedQuestions = questions[candidate.candidate_id];
  const hasCachedQuestions = cachedQuestions && cachedQuestions.length > 0;

  return (
    <div className="page-detail">
      <button className="btn-ghost btn-sm" onClick={() => navigate("/dashboard")} style={{ marginBottom: "1.5rem" }}>
        ← Back to Dashboard
      </button>

      <div className="hero-card">
        <div className="hero-avatar">
          {candidate.name.charAt(0).toUpperCase()}
        </div>
        <div className="hero-info">
          <h2 className="hero-name">{candidate.name}</h2>
          <div className="hero-meta">
            <span className="hero-rank">Rank #{candidate.rank}</span>
            <span className="hero-sep">·</span>
            <span className="hero-score">{Math.round((candidate.fit_score ?? 0) * 100)}% Match</span>
          </div>
        </div>
        <div className="hero-actions">
          <FeedbackButtons candidateId={candidate.candidate_id} currentDecision={candidate.decision} />
        </div>
      </div>

      <div className="detail-tabs">
        <button
          className={`tab-btn ${tab === "why" ? "active" : ""}`}
          onClick={() => setTab("why")}
        >
          Why this score?
        </button>
        <button
          className={`tab-btn ${tab === "questions" ? "active" : ""}`}
          onClick={() => setTab("questions")}
        >
          Interview Questions
        </button>
      </div>

      <div className="detail-body">
        {tab === "why" ? (
          <WhyPanel features={candidate.features} name={candidate.name} />
        ) : (
          <AdaptiveQs
            candidateId={candidate.candidate_id}
            jdId={jdId}
            cachedQuestions={hasCachedQuestions ? cachedQuestions : undefined}
          />
        )}
      </div>
    </div>
  );
}
