import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStore, getPersistedJdId } from "../store/useStore";
import { ScoreCard }     from "../components/ScoreCard";
import { CriteriaDrift } from "../components/CriteriaDrift";
import { BiasPanel }     from "../components/BiasPanel";
import { getImportances, forceRetrain, uploadResumeFiles, listCandidates, exportShortlist } from "../api/client";

export default function Dashboard() {
  const navigate = useNavigate();
  const {
    candidates, jdId, criteria, importances, modelVersion,
    retrainFlash, clearFlash,
    setImportances, applyRetrain, setCandidates, questions, setJD,
  } = useStore();

  const fileRef   = useRef<HTMLInputElement>(null);
  const [uploading,  setUploading]  = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [showBias,   setShowBias]   = useState(false);

  // ── Session recovery ────────────────────────────────────────────────────
  useEffect(() => {
    if (jdId && candidates.length > 0) return;
    const savedId = jdId || getPersistedJdId();
    if (!savedId) return;
    setRecovering(true);
    if (!jdId) setJD(savedId, "", { skills: [], exp_years: 0, level: "", keywords: [] });
    Promise.all([
      listCandidates(savedId),
      getImportances(savedId),
    ]).then(([cr, imp]) => {
      if (cr.candidates?.length) setCandidates(cr.candidates, questions);
      setImportances(imp);
    }).catch(e => console.error("Recovery:", e))
    .finally(() => setRecovering(false));
  }, []);

  useEffect(() => {
    if (!jdId) return;
    getImportances(jdId).then(setImportances).catch(() => {});
  }, [jdId]);

  useEffect(() => {
    if (retrainFlash) {
      const t = setTimeout(clearFlash, 1600);
      return () => clearTimeout(t);
    }
  }, [retrainFlash]);

  if (recovering) return (
    <div className="page-empty">
      <div className="spinner" style={{ width: 24, height: 24 }} />
      <span>Restoring session…</span>
    </div>
  );

  if (!jdId || candidates.length === 0) return (
    <div className="page-empty">
      <div className="empty-icon">📋</div>
      <p>No candidates loaded.</p>
      <button className="btn btn-primary" onClick={() => navigate("/")}>← Start a new session</button>
    </div>
  );

  const approved = candidates.filter(c => c.decision === "approve").length;
  const rejected = candidates.filter(c => c.decision === "reject").length;
  const decided  = candidates.filter(c => c.decision).length;

  async function handleForceRetrain() {
    if (!jdId || retraining) return;
    setRetraining(true);
    try {
      const res = await forceRetrain(jdId);
      applyRetrain(res.new_ranking, res.importances);
      const imp = await getImportances(jdId);
      setImportances(imp);
    } catch (e) { console.error(e); }
    finally { setRetraining(false); }
  }

  async function handleUploadMore(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files?.length || !jdId) return;
    setUploading(true);
    try {
      const res = await uploadResumeFiles(jdId, Array.from(files));
      setCandidates(res.ranked, { ...questions, ...res.questions });
    } catch (err) { console.error(err); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function handleExport() {
    if (!jdId) return;
    try {
      const blob = await exportShortlist(jdId);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = "hireloop-shortlist.csv";
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
  }

  return (
    <div className="page-dashboard">
      {/* ── Main column ─────────────────────────────────────────────────── */}
      <div>
        <div className="dash-header">
          <div>
            <div className="dash-title">Candidate Rankings</div>
            <div className="dash-meta">
              {criteria?.level && <span style={{ textTransform: "capitalize" }}>{criteria.level} · </span>}
              {criteria?.skills?.slice(0, 2).join(", ")}
              {criteria?.exp_years ? ` · ${criteria.exp_years}+ yrs` : ""}
            </div>
          </div>
          <div className="dash-actions">
            <button className="btn btn-secondary btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? <><span className="spinner" /> Uploading…</> : "↑ Upload more"}
            </button>
            <input type="file" multiple accept=".txt,.pdf" ref={fileRef} style={{ display: "none" }} onChange={handleUploadMore} />
            <button className="btn btn-secondary btn-sm" onClick={handleForceRetrain} disabled={retraining}>
              {retraining ? <><span className="spinner" /> Retraining…</> : "⟳ Retrain"}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={handleExport} title="Export shortlist as CSV">
              ↓ Export
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate("/")}>+ New JD</button>
          </div>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total</div>
            <div className="stat-value">{candidates.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Approved</div>
            <div className="stat-value c-green">{approved}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Rejected</div>
            <div className="stat-value c-red">{rejected}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Model</div>
            <div className="stat-value c-indigo">v{modelVersion || "—"}</div>
          </div>
        </div>

        {/* Column headers */}
        <div className="list-header">
          <span>Candidate</span>
          <span>Score · Δ Rank · Decision</span>
        </div>

        <div className="cand-list">
          {candidates.map(c => (
            <ScoreCard key={c.candidate_id} candidate={c} globalFlash={retrainFlash} />
          ))}
        </div>

        {/* Bias panel — show toggle after 5 decisions */}
        {decided >= 5 && (
          <div style={{ marginTop: 20 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowBias(v => !v)}
              style={{ color: "var(--indigo-600)", marginBottom: 10 }}
            >
              {showBias ? "▲ Hide" : "▼ Show"} bias analysis
            </button>
            {showBias && (
              <div className="card card-p-sm">
                <BiasPanel candidates={candidates} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div className="sidebar-sticky">
        <CriteriaDrift importances={importances} />

        {/* Role card */}
        <div className="role-card">
          <div className="section-label" style={{ marginBottom: 8 }}>Role summary</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 7, fontSize: 13, marginBottom: 10 }}>
            <SideRow label="Level"  val={criteria?.level ?? "—"} />
            <SideRow label="Exp"    val={`${criteria?.exp_years ?? 0}+ years`} />
          </div>
          {(criteria?.skills?.length ?? 0) > 0 && (
            <>
              <div className="divider" style={{ margin: "10px 0" }} />
              <div className="section-label" style={{ marginBottom: 6 }}>Required skills</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {criteria?.skills?.map((s: string) => (
                  <span key={s} className="chip chip-skill">{s}</span>
                ))}
              </div>
            </>
          )}
          {(criteria?.keywords?.length ?? 0) > 0 && (
            <>
              <div className="section-label" style={{ marginTop: 10, marginBottom: 6 }}>Keywords</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {criteria?.keywords?.map((k: string) => (
                  <span key={k} className="chip chip-keyword">{k}</span>
                ))}
              </div>
            </>
          )}
          <div className="divider" style={{ margin: "12px 0" }} />
          <button
            className="btn btn-secondary btn-sm"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={() => navigate("/compare")}
          >
            ⇄ Compare candidates
          </button>
        </div>

        <p style={{ fontSize: 11, color: "var(--text-tertiary)", textAlign: "center", lineHeight: 1.6 }}>
          Click any candidate to see the score breakdown, SHAP attribution, and interview questions.
        </p>
      </div>
    </div>
  );
}

function SideRow({ label, val }: { label: string; val: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--text-tertiary)", fontSize: 12 }}>{label}</span>
      <span style={{ fontWeight: 500, textTransform: "capitalize" }}>{val}</span>
    </div>
  );
}
