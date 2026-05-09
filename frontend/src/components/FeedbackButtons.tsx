import { useState } from "react";
import { submitFeedback } from "../api/client";
import { useStore } from "../store/useStore";

interface Props {
  candidateId: string;
  currentDecision?: "approve" | "reject" | null;
  onFeedback?: (decision: "approve" | "reject", retrained: boolean) => void;
  compact?: boolean;
}

export function FeedbackButtons({ candidateId, currentDecision, onFeedback, compact }: Props) {
  const [decision, setDecision] = useState<"approve" | "reject" | null>(currentDecision ?? null);
  const [loading, setLoading]   = useState(false);
  const { jdId, applyRetrain, updateFeedbackCount, updateDecision } = useStore();

  async function handleClick(e: React.MouseEvent, d: "approve" | "reject") {
    e.stopPropagation();
    if (!jdId || loading || decision === d) return;
    setLoading(true);
    try {
      const res = await submitFeedback(jdId, candidateId, d);
      setDecision(d);
      updateDecision(candidateId, d);
      updateFeedbackCount(res.feedback_count);
      if (res.retrain_triggered && res.new_ranking && res.importances) {
        applyRetrain(res.new_ranking, res.importances);
      }
      onFeedback?.(d, res.retrain_triggered);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`feedback-buttons ${compact ? "compact" : ""}`}>
      <button
        className={`btn-approve ${decision === "approve" ? "active" : ""}`}
        onClick={(e) => handleClick(e, "approve")}
        disabled={loading}
        aria-label="Approve candidate"
        title="Approve"
      >
        <span className="btn-icon">✓</span>
        <span className="btn-label">Approve</span>
      </button>
      <button
        className={`btn-reject ${decision === "reject" ? "active" : ""}`}
        onClick={(e) => handleClick(e, "reject")}
        disabled={loading}
        aria-label="Reject candidate"
        title="Reject"
      >
        <span className="btn-icon">✕</span>
        <span className="btn-label">Reject</span>
      </button>
    </div>
  );
}
