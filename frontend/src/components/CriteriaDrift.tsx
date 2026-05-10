import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
  LineChart, Line
} from "recharts";
import type { ModelImportances } from "../types";

const FEATURE_LABELS: Record<string, string> = {
  skill_overlap:   "Skill Overlap",
  semantic_sim:    "Semantic Match",
  exp_gap:         "Experience Fit",
  keyword_density: "Keyword Density",
};

const COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#34d399"];

interface Props {
  importances: ModelImportances | null;
  feedbackNeeded?: number;
}

export function CriteriaDrift({ importances, feedbackNeeded = 5 }: Props) {
  if (!importances) {
    return (
      <div className="criteria-drift empty">
        <p className="drift-hint">
          Give feedback on {feedbackNeeded} candidates to unlock the Criteria Drift panel.
        </p>
      </div>
    );
  }

  const v1Importances = importances.history.length > 0 
    ? importances.history[0].importances 
    : importances.importances;

  const data = Object.entries(importances.importances).map(([key, val], i) => {
    const v1Val = v1Importances[key] ?? val;
    const delta = Math.round((val - v1Val) * 100);
    return {
      name:  FEATURE_LABELS[key] ?? key,
      value: Math.round(val * 100),
      delta: delta,
      color: COLORS[i % COLORS.length],
    };
  });

  const aucData = importances.history
    .filter(h => h.val_auc != null)
    .map(h => ({ version: `v${h.version}`, auc: h.val_auc as number }));

  return (
    <div className="criteria-drift">
      <div className="drift-header">
        <div>
          <h3 className="drift-title">What you actually care about</h3>
          <p className="drift-subtitle">
            Model v{importances.version} · {importances.feedback_count} decisions 
            {importances.val_auc != null ? ` · AUC ${(importances.val_auc).toFixed(2)}` : ""}
          </p>
        </div>
        {importances.version > 1 && (
          <span className="drift-badge">Adapted ✦</span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border-strong)" />
          <XAxis
            type="number"
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
            domain={[0, 100]}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: "var(--text-primary)", fontSize: 12, fontWeight: 500 }}
            axisLine={false}
            tickLine={false}
            width={100}
          />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)" }}
            labelStyle={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: "4px" }}
            formatter={(v: number, name: string, props: any) => {
              const d = props.payload.delta;
              const deltaStr = d > 0 ? ` (+${d}%)` : d < 0 ? ` (${d}%)` : "";
              return [`${v}%${deltaStr}`, "Weight"];
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {importances.history.length > 1 && (
        <div className="drift-history">
          <p className="history-label">Version history</p>
          <div className="history-list">
            {importances.history.slice(-4).map((v) => (
              <div key={v.version} className="history-item">
                <span className="history-v">v{v.version}</span>
                <span className="history-count">{v.feedback_count} decisions</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {aucData.length > 1 && (
        <div className="auc-sparkline" style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
          <p className="history-label" style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Model AUC Trend</span>
            <span style={{ color: "var(--indigo-600)", fontWeight: 600 }}>{(aucData[aucData.length - 1].auc).toFixed(2)}</span>
          </p>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={aucData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <Line type="monotone" dataKey="auc" stroke="var(--indigo-600)" strokeWidth={2} dot={{ r: 3, fill: "var(--surface)", strokeWidth: 2 }} activeDot={{ r: 5 }} />
              <Tooltip 
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: "11px", padding: "4px 8px" }}
                formatter={(v: number) => [v.toFixed(3), "AUC"]}
                labelStyle={{ display: "none" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
