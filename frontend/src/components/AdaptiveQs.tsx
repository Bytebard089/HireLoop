import { useEffect, useState } from "react";
import { getQuestions } from "../api/client";
import type { Question } from "../types";
import type { SkillGap } from "../api/client";

function tagClass(tag: string): string {
  if (tag.startsWith("gap"))     return "gap";
  if (tag.startsWith("depth"))   return "depth";
  if (tag.startsWith("project")) return "project";
  if (tag.includes("design"))    return "design";
  return "general";
}
function tagLabel(tag: string): string {
  return tag
    .replace("gap:", "Gap: ")
    .replace("depth:", "Depth: ")
    .replace("project:", "Project: ")
    .replace("system_design", "System Design");
}

function severityClass(severity: string): string {
  if (severity === "high") return "severity-high";
  if (severity === "medium") return "severity-medium";
  return "severity-low";
}

/**
 * Detect if cached questions are stale (old generic format).
 * Old questions have tags like "general" and generic text; new ones have
 * "gap:", "depth:", "project:", or "system_design" tags.
 */
function isStaleCache(qs: Question[] | undefined): boolean {
  if (!qs || qs.length === 0) return true;
  // If every question has tag "general", it's the old generic fallback
  return qs.every(q => tagClass(q.tag) === "general");
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
  cachedSkillGaps?: SkillGap[];
}

export function AdaptiveQs({ candidateId, jdId, cachedQuestions, cachedSkillGaps }: Props) {
  const [questions, setQuestions] = useState<Question[]>(cachedQuestions ?? []);
  const [skillGaps, setSkillGaps] = useState<SkillGap[]>(cachedSkillGaps ?? []);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState<string | null>(null);

  useEffect(() => {
    // If cached questions are good (not stale generic ones), use them
    if (cachedQuestions && cachedQuestions.length > 0 && !isStaleCache(cachedQuestions)) {
      setQuestions(cachedQuestions);
      setSkillGaps(cachedSkillGaps ?? []);
      setLoading(false);
      return;
    }

    // Otherwise, always fetch fresh personalized questions from the API
    setLoading(true);
    setError(null);
    getQuestions(candidateId, jdId)
      .then(res => {
        setQuestions(res.questions ?? []);
        setSkillGaps(res.skill_gaps ?? []);
      })
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
      {/* Skill Gaps Section */}
      {skillGaps.length > 0 && (
        <div className="skill-gaps-section">
          <div className="section-label" style={{ marginBottom: 8 }}>
            Resume-specific skill gaps
          </div>
          <div className="skill-gaps-list">
            {skillGaps.map((gap, i) => (
              <div key={i} className={`skill-gap-item ${severityClass(gap.severity)}`}>
                <div className="skill-gap-header">
                  <span className="skill-gap-name">{gap.skill}</span>
                  <span className={`skill-gap-severity ${severityClass(gap.severity)}`}>
                    {gap.severity}
                  </span>
                </div>
                {gap.context && (
                  <p className="skill-gap-context">{gap.context}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Questions Section */}
      <div className="section-label" style={{ marginBottom: 10, marginTop: skillGaps.length > 0 ? 20 : 0 }}>
        Personalized interview questions — based on this candidate's resume
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
