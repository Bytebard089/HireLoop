import { useEffect, useState } from "react";
import { getQuestions } from "../api/client";
import type { Question } from "../types";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      [elemName: string]: any;
    }
  }
}

const TAG_COLORS: Record<string, string> = {
  gap:           "#ef4444",
  depth:         "#f59e0b",
  system_design: "#8b5cf6",
  general:       "#6b7280",
};

function tagColor(tag: string): string {
  const prefix = tag.split(":")[0];
  return TAG_COLORS[prefix] ?? TAG_COLORS.general;
}

interface Props {
  candidateId: string;
  jdId: string;
  cachedQuestions?: Question[];
}

export function AdaptiveQs({ candidateId, jdId, cachedQuestions }: Props) {
  const [questions, setQuestions] = useState<Question[]>(cachedQuestions ?? []);
  const [loading, setLoading]     = useState(!cachedQuestions?.length);
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    if (cachedQuestions?.length) return;
    setLoading(true);
    getQuestions(candidateId, jdId)
      .then((res) => setQuestions(res.questions))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [candidateId, jdId]);

  if (loading) {
    return (
      <div className="adaptive-qs">
        {[1, 2, 3].map((i) => (
          <div key={i} className="question-skeleton">
            <div className="skeleton-tag" />
            <div className="skeleton-text" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return <div className="adaptive-qs error-msg">Failed to load questions: {error}</div>;
  }

  return (
    <div className="adaptive-qs">
      {questions.map((q: Question, i: number) => (
        <div key={i} className="question-card">
          <span
            className="question-tag"
            style={{ background: tagColor(q.tag) }}
          >
            {q.tag}
          </span>
          <p className="question-text">{q.question}</p>
        </div>
      ))}
    </div>
  );
}
