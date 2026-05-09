import { useEffect, useRef, useState } from "react";
import type { Candidate } from "../types";
import { FeedbackButtons } from "./FeedbackButtons";
import { Link } from "react-router-dom";

interface Props {
  candidate: Candidate;
  flash?: boolean;
}

export function ScoreCard({ candidate, flash }: Props) {
  const [flashClass, setFlashClass] = useState("");
  const prevRank = useRef(candidate.rank);

  useEffect(() => {
    const rankChanged = candidate.rank !== prevRank.current;
    prevRank.current = candidate.rank;

    if (!rankChanged || !flash) {
      // No rank change for this card, or no retrain event — don't flash
      setFlashClass("");
      return;
    }

    const delta = candidate.rank_change ?? 0;
    if (delta > 0) {
      setFlashClass("flash-up");
    } else if (delta < 0) {
      setFlashClass("flash-down");
    } else {
      setFlashClass("");
      return;
    }

    const t = setTimeout(() => setFlashClass(""), 800);
    return () => clearTimeout(t);
  }, [candidate.rank, candidate.rank_change, flash]);

  const scorePercent = Math.round((candidate.fit_score ?? 0) * 100);
  const margin = 2 + (String(candidate.candidate_id).charCodeAt(0) % 5);
  const delta = candidate.rank_change ?? 0;

  return (
    <div className={`score-card ${flashClass}`}>
      <div className="rank-badge">#{candidate.rank}</div>

      <div className="card-body">
        <Link to={`/candidate/${candidate.candidate_id}`} className="candidate-name">
          {candidate.name}
        </Link>

        <div className="score-bar-wrap">
          <div className="score-bar-bg">
            <div className="score-bar" style={{ width: `${scorePercent}%` }} />
            <div className="score-band" style={{
              left: `${Math.max(0, scorePercent - margin)}%`,
              width: `${Math.min(100, scorePercent + margin) - Math.max(0, scorePercent - margin)}%`,
            }} />
          </div>
          <span className="score-label">{scorePercent}% <span className="score-margin">±{margin}</span></span>
        </div>
      </div>

      <div className="card-right">
        <div className={`rank-delta ${delta > 0 ? "up" : delta < 0 ? "down" : "same"}`}>
          {delta > 0 ? `▲${delta}` : delta < 0 ? `▼${Math.abs(delta)}` : "—"}
        </div>
        <FeedbackButtons candidateId={candidate.candidate_id} currentDecision={candidate.decision} />
      </div>
    </div>
  );
}
