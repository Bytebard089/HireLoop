import type { Features } from "../types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from "recharts";

interface Props { features: Features; score: number; }

const BASE_SCORE = 0.50;

// Approximate SHAP-like attribution from raw feature values
function computeShap(features: Features, finalScore: number) {
  const weights = { skill_overlap: 0.40, semantic_sim: 0.30, exp_gap: 0.20, keyword_density: 0.10 };
  const labels  = { skill_overlap: "Skill Overlap", semantic_sim: "Semantic Match", exp_gap: "Experience Fit", keyword_density: "Keywords" };
  const items: { name: string; value: number; abs: number }[] = [];

  (["skill_overlap", "semantic_sim", "exp_gap", "keyword_density"] as const).forEach(k => {
    const raw = (features as any)[k] ?? 0;
    const v   = k === "exp_gap" ? (1 - raw) : raw;
    const contribution = (v - 0.5) * weights[k];
    items.push({ name: labels[k], value: parseFloat(contribution.toFixed(3)), abs: Math.abs(contribution) });
  });

  // Scale so contributions sum to finalScore - BASE_SCORE
  const total = items.reduce((s, i) => s + i.value, 0);
  const diff  = finalScore - BASE_SCORE;
  const scale = total !== 0 ? diff / total : 1;
  return items.map(i => ({ ...i, value: parseFloat((i.value * scale).toFixed(3)) }));
}

export function ShapPanel({ features, score }: Props) {
  const data = computeShap(features, score);

  return (
    <div>
      <div className="section-label" style={{ marginBottom: 4 }}>Feature attribution (approximate)</div>
      <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 12, lineHeight: 1.55 }}>
        How each feature pushed the score above or below the baseline of {(BASE_SCORE * 100).toFixed(0)}%.
        Contributions are approximated from feature weights — not computed via Shapley values.
      </p>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 20 }}>
          <XAxis type="number" tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={96} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Attribution"]}
            contentStyle={{ background: "white", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
          />
          <ReferenceLine x={0} stroke="var(--border-strong)" />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.value >= 0 ? "#6366F1" : "#EF4444"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 11, color: "var(--text-tertiary)" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, background: "#6366F1", borderRadius: 2, display: "inline-block" }} />
          Pushed score up
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, background: "#EF4444", borderRadius: 2, display: "inline-block" }} />
          Pushed score down
        </span>
      </div>
    </div>
  );
}
