import type { Candidate } from "../types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts";

interface Props { candidates: Candidate[]; }

function bandLabel(years: number): string {
  if (years < 2)  return "0–2 yrs";
  if (years < 5)  return "2–5 yrs";
  if (years < 9)  return "5–9 yrs";
  return "9+ yrs";
}

export function BiasPanel({ candidates }: Props) {
  const decided = candidates.filter(c => c.decision);
  if (decided.length < 5) {
    return (
      <div style={{ textAlign: "center", color: "var(--text-tertiary)", fontSize: 12, padding: "1.25rem", lineHeight: 1.6 }}>
        Need at least 5 feedback decisions to run bias analysis.
        <br />({decided.length} / 5 so far)
      </div>
    );
  }

  // Group by experience band
  const bands: Record<string, { approve: number; total: number }> = {};
  for (const c of decided) {
    const yrs  = c.features?.resume_years ?? 0;
    const band = bandLabel(yrs);
    if (!bands[band]) bands[band] = { approve: 0, total: 0 };
    bands[band].total++;
    if (c.decision === "approve") bands[band].approve++;
  }

  const data = Object.entries(bands)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([band, { approve, total }]) => ({
      band,
      rate: Math.round((approve / total) * 100),
      total,
    }));

  const overallRate = Math.round((decided.filter(c => c.decision === "approve").length / decided.length) * 100);
  const maxDiff     = Math.max(...data.map(d => Math.abs(d.rate - overallRate)));
  const hasBias     = maxDiff >= 25 && data.length >= 2;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Experience bias check</div>
        {hasBias ? (
          <span className="badge badge-amber">⚠ Potential bias</span>
        ) : (
          <span className="badge badge-green">✓ Balanced</span>
        )}
      </div>
      <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 12, lineHeight: 1.55 }}>
        Approval rate by experience band. Dashed line = overall average ({overallRate}%).
        A gap &gt;25% may indicate unintended seniority bias.
      </p>
      <ResponsiveContainer width="100%" height={130}>
        <BarChart data={data} margin={{ top: 4, right: 10, bottom: 0, left: 0 }}>
          <XAxis dataKey="band" tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={v => `${v}%`} domain={[0, 100]} tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} axisLine={false} tickLine={false} width={32} />
          <Tooltip
            formatter={(v: number, _: string, p: any) => [`${v}% (${p.payload.total} candidates)`, "Approval rate"]}
            contentStyle={{ background: "white", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
          />
          <ReferenceLine y={overallRate} stroke="#6366F1" strokeDasharray="4 3" strokeWidth={1.5} />
          <Bar dataKey="rate" radius={[4, 4, 0, 0]} barSize={28}>
            {data.map((d, i) => (
              <Cell key={i} fill={Math.abs(d.rate - overallRate) >= 25 ? "#F59E0B" : "#6366F1"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {hasBias && (
        <div style={{
          background: "var(--amber-50)", border: "1px solid var(--amber-100)",
          borderRadius: "var(--r-sm)", padding: "9px 12px",
          fontSize: 12, color: "var(--amber-600)", lineHeight: 1.55, marginTop: 10
        }}>
          Approval rate varies by &gt;{maxDiff}% across experience bands. Review decisions to ensure criteria is being applied consistently.
        </div>
      )}
    </div>
  );
}
