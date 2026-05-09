import { useEffect, useState } from "react";
import { getQuestions } from "../api/client";
import type { Question } from "../types";

function tagClass(tag: string): string {
  if (tag.startsWith("gap"))    return "gap";
  if (tag.startsWith("depth"))  return "depth";
  if (tag.includes("design"))   return "design";
  return "general";
}
function tagLabel(tag: string): string {
  return tag.replace("gap:", "Gap: ").replace("depth:", "Depth: ").replace("system_design", "System Design");
}

function Skeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {[70, 85, 65].map((w, i) => (
        <div key={i} className="sk-block">
          <div className="sk-bar" style={{ width: "60px", marginBottom: 10, borderRadius: 99 }} />
          <div className="sk-bar" style={{ width: `${w}%`, marginBottom: 6 }} />
          <div className="sk-bar" style={{ width: `${w - 15}%` }} />
        </div>
      ))}
    </div>
  );
}

interface Props {
  candidateId:     string;
  jdId:            string;
  cachedQuestions?: Question[];
}

export function AdaptiveQs({ candidateId, jdId, cachedQuestions }: Props) {
  const [questions, setQuestions] = useState<Question[]>(cachedQuestions ?? []);
  const [loading,   setLoading]   = useState(!cachedQuestions?.length);
  const [error,     setError]     = useState<string | null>(null);

  useEffect(() => {
    // Always fetch if no cached questions — fixes the empty-cache bug
    if (cachedQuestions && cachedQuestions.length > 0) {
      setQuestions(cachedQuestions);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getQuestions(candidateId, jdId)
      .then(res => setQuestions(res.questions ?? []))
      .catch(e  => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, [candidateId, jdId]);

  if (loading) return <Skeleton />;

  if (error) {
    return (
      <div className="error-box">⚠ {error}</div>
    );
  }

  if (!questions.length) {
    return (
      <div style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "2rem", fontSize: 13 }}>
        No questions generated yet.
      </div>
    );
  }

  return (
    <div>
      <div className="section-label" style={{ marginBottom: 10 }}>
        Adaptive interview questions — generated from this candidate's specific gaps
      </div>
      <div className="q-list">
        {questions.map((q, i) => (
          <div key={i} className="q-card">
            <span className={`q-tag ${tagClass(q.tag)}`}>{tagLabel(q.tag)}</span>
            <p className="q-text">{q.question}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
