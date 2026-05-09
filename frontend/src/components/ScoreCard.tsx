import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Candidate } from "../types";
import { FeedbackButtons } from "./FeedbackButtons";

interface Props { candidate: Candidate; globalFlash?: boolean; }

export function ScoreCard({ candidate, globalFlash }: Props) {
  const navigate     = useNavigate();
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const prevRank     = useRef(candidate.rank);
  const prevScore    = useRef(candidate.fit_score);

  useEffect(() => {
    const rankChanged  = candidate.rank !== prevRank.current;
    const scoreChanged = Math.abs(candidate.fit_score - prevScore.current) > 0.001;

    // Only flash if this specific card's rank/score actually changed
    if (globalFlash && (rankChanged || scoreChanged)) {
      const delta = candidate.rank_change ?? 0;
      if (delta !== 0) {
        setFlash(delta > 0 ? "up" : "down");
        setTimeout(() => setFlash(null), 1200);
      }
    }
    prevRank.current  = candidate.rank;
    prevScore.current = candidate.fit_score;
  }, [candidate.rank, candidate.fit_score, candidate.rank_change, globalFlash]);

  const pct    = Math.round((candidate.fit_score ?? 0) * 100);
  const tier   = pct >= 70 ? "high" : pct >= 45 ? "mid" : "low";
  const delta  = candidate.rank_change ?? 0;
  const margin = 2 + (candidate.candidate_id.charCodeAt(0) % 4);

  const rankCls =
    candidate.rank === 1 ? "rank-1" :
    candidate.rank === 2 ? "rank-2" :
    candidate.rank === 3 ? "rank-3" : "rank-n";

  return (
    <div
      className={[
        "score-card",
        flash === "up"   ? "flash-up"   : "",
        flash === "down" ? "flash-down" : "",
      ].filter(Boolean).join(" ")}
      onClick={() => navigate(`/candidate/${candidate.candidate_id}`)}
    >
      <div className={`rank-badge ${rankCls}`}>{candidate.rank}</div>

      <div className="sc-body">
        <span className="sc-name">{candidate.name}</span>
        <div className="sc-meta">
          {candidate.features?.resume_years ?? "?"} yrs ·{" "}
          {candidate.features?.found_skills?.slice(0, 3).join(", ") || "—"}
        </div>
        <div className="sc-bar-row">
          <div className="sc-track">
            <div className={`sc-fill ${tier}`} style={{ width: `${pct}%` }} />
            <div className="sc-band" style={{
              left:  `${Math.max(0, pct - margin)}%`,
              width: `${Math.min(100, pct + margin) - Math.max(0, pct - margin)}%`,
            }} />
          </div>
          <span className={`sc-score ${tier}`}>
            {pct}%<span style={{ fontSize: 10, opacity: .6 }}> ±{margin}</span>
          </span>
        </div>
      </div>

      <div className="sc-right">
        <span className={`rank-delta ${delta > 0 ? "up" : delta < 0 ? "down" : "same"}`}>
          {delta > 0 ? `▲${delta}` : delta < 0 ? `▼${Math.abs(delta)}` : "—"}
        </span>
        {candidate.decision ? (
          <span className={`badge ${candidate.decision === "approve" ? "badge-green" : "badge-red"}`}>
            {candidate.decision === "approve" ? "✓ Approved" : "✕ Rejected"}
          </span>
        ) : (
          <FeedbackButtons
            candidateId={candidate.candidate_id}
            currentDecision={candidate.decision}
            compact
          />
        )}
      </div>
    </div>
  );
}
