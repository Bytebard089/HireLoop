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
    <div>
      <div style={{ fontSize: "14px", fontWeight: 700, marginBottom: "1.25rem" }}>Why this score? — {name}</div>
      <div className="why-bars">
        {FEATURE_META.map(({ key, label, description, invert }) => {
          const raw = (features[key] as number) ?? 0;
          const display = invert ? 1 - raw : raw;
          const pct = Math.round(display * 100);
          const tier = pct >= 70 ? "high" : pct >= 40 ? "mid" : "low";
          return (
            <div key={key} className="why-row">
              <div className="why-top">
                <div className="why-name">{label}</div>
                <div className={`why-pct ${tier}`}>{pct}%</div>
              </div>
              <div className="why-desc">{description}</div>
              <div className="why-track">
                <div className={`why-fill ${tier}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {features.missing_skills && features.missing_skills.length > 0 && (
        <div className="skill-section">
          <div className="skill-section-label">Skill Gaps</div>
          <div className="chip-wrap">
            {features.missing_skills.map((s) => (
              <span key={s} className="chip chip-missing">{s}</span>
            ))}
          </div>
        </div>
      )}

      {features.found_skills && features.found_skills.length > 0 && (
        <div className="skill-section">
          <div className="skill-section-label">Matching Skills</div>
          <div className="chip-wrap">
            {features.found_skills.map((s) => (
              <span key={s} className="chip chip-found">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
