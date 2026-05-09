import type { Features } from "../types";

const FEATURE_META: { key: keyof Features; label: string; description: string; invert?: boolean }[] = [
  { key: "skill_overlap",   label: "Skill Overlap",    description: "Jaccard match on required skills" },
  { key: "semantic_sim",    label: "Semantic Match",   description: "Cross-encoder similarity score" },
  { key: "exp_gap",         label: "Experience Fit",   description: "Years alignment (lower gap = better)", invert: true },
  { key: "keyword_density", label: "Keyword Density",  description: "JD vocabulary present in resume" },
];

interface Props {
  features: Features;
  name: string;
}

export function WhyPanel({ features, name }: Props) {
  return (
    <div className="why-panel">
      <h3 className="panel-title">Why this score? — {name}</h3>
      <div className="feature-bars">
        {FEATURE_META.map(({ key, label, description, invert }) => {
          const raw = (features[key] as number) ?? 0;
          const display = invert ? 1 - raw : raw;
          const pct = Math.round(display * 100);
          const tier = pct >= 70 ? "high" : pct >= 40 ? "mid" : "low";
          return (
            <div key={key} className="feature-row">
              <div className="feature-label">
                <span>{label}</span>
                <span className="feature-desc">{description}</span>
              </div>
              <div className="feature-bar-track">
                <div className={`feature-bar-fill tier-${tier}`} style={{ width: `${pct}%` }} />
              </div>
              <span className={`feature-pct tier-${tier}`}>{pct}%</span>
            </div>
          );
        })}
      </div>

      {features.missing_skills && features.missing_skills.length > 0 && (
        <div className="skill-gap-section">
          <h4>Skill Gaps</h4>
          <div className="skill-chips">
            {features.missing_skills.map((s) => (
              <span key={s} className="chip chip-missing">{s}</span>
            ))}
          </div>
        </div>
      )}

      {features.found_skills && features.found_skills.length > 0 && (
        <div className="skill-gap-section">
          <h4>Matching Skills</h4>
          <div className="skill-chips">
            {features.found_skills.map((s) => (
              <span key={s} className="chip chip-found">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
