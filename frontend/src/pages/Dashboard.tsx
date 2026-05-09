import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useStore, getPersistedJdId } from "../store/useStore";
import { ScoreCard } from "../components/ScoreCard";
import { CriteriaDrift } from "../components/CriteriaDrift";
import { getImportances, forceRetrain, uploadResumeFiles, listCandidates } from "../api/client";

export default function Dashboard() {
  const { candidates, jdId, importances, modelVersion, retrainFlash, clearFlash, setImportances, applyRetrain, setCandidates, questions, setJD } = useStore();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [recovering, setRecovering] = useState(false);

  // ── Recover state on page refresh ────────────────────────────────────────
  useEffect(() => {
    if (jdId && candidates.length > 0) return; // already loaded
    const savedJdId = jdId || getPersistedJdId();
    if (!savedJdId) return;

    setRecovering(true);
    // Restore jdId in store if not set (page refresh scenario)
    if (!jdId) {
      setJD(savedJdId, "", { skills: [], exp_years: 0, level: "", keywords: [] });
    }

    listCandidates(savedJdId)
      .then((res) => {
        if (res.candidates?.length) {
          setCandidates(res.candidates, questions);
        }
      })
      .catch((e) => console.error("Failed to recover candidates:", e))
      .finally(() => setRecovering(false));
  }, []);

  useEffect(() => {
    if (!jdId) return;
    getImportances(jdId).then(setImportances).catch(() => {});
  }, [jdId]);

  useEffect(() => {
    if (retrainFlash) {
      const t = setTimeout(clearFlash, 1500);
      return () => clearTimeout(t);
    }
  }, [retrainFlash]);

  if (recovering) {
    return (
      <div className="page-empty">
        <p>Loading candidates…</p>
      </div>
    );
  }

  if (!jdId || candidates.length === 0) {
    return (
      <div className="page-empty">
        <p>No candidates loaded. <button className="btn-link" onClick={() => navigate("/")}>← Start over</button></p>
      </div>
    );
  }

  async function handleForceRetrain() {
    if (!jdId) return;
    try {
      const res = await forceRetrain(jdId);
      applyRetrain(res.new_ranking, res.importances);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleUploadMore(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || !files.length || !jdId) return;
    setUploading(true);
    try {
      const res = await uploadResumeFiles(jdId, Array.from(files));
      setCandidates(res.ranked, { ...questions, ...res.questions });
    } catch (e) {
      console.error("Upload failed", e);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="page-dashboard">
      <div className="dashboard-main">
        <div className="dashboard-header">
          <div>
            <h2 className="section-title">Candidate Rankings</h2>
            <p className="section-sub">{candidates.length} candidates · Model v{modelVersion}</p>
          </div>
          <div className="header-actions">
            <button className="btn-ghost btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? "Uploading..." : "↑ Upload More"}
            </button>
            <input 
              type="file" 
              multiple 
              accept=".txt,.pdf" 
              ref={fileRef} 
              style={{ display: "none" }} 
              onChange={handleUploadMore} 
            />
            <button className="btn-ghost btn-sm" onClick={handleForceRetrain}>
              ↺ Force Retrain
            </button>
            <button className="btn-ghost btn-sm" onClick={() => navigate("/")}>
              + New JD
            </button>
          </div>
        </div>

          <DashboardStats candidates={candidates} modelVersion={modelVersion} />

        <div className="candidate-list">
          {candidates.map((c) => (
            <ScoreCard key={c.candidate_id} candidate={c} flash={retrainFlash} />
          ))}
        </div>
      </div>

      <aside className="dashboard-sidebar">
        <CriteriaDrift importances={importances} />
      </aside>
    </div>
  );
}

function DashboardStats({ candidates, modelVersion }: { candidates: any[], modelVersion: number }) {
  const total = candidates.length;
  const approved = candidates.filter(c => c.decision === "approve").length;
  const rejected = candidates.filter(c => c.decision === "reject").length;

  return (
    <div className="stats-row">
      <div className="stat-box">
        <span className="stat-label">Candidates</span>
        <span className="stat-val">{total}</span>
      </div>
      <div className="stat-box">
        <span className="stat-label">Approved</span>
        <span className="stat-val text-green">{approved}</span>
      </div>
      <div className="stat-box">
        <span className="stat-label">Rejected</span>
        <span className="stat-val text-red">{rejected}</span>
      </div>
      <div className="stat-box">
        <span className="stat-label">Model</span>
        <span className="stat-val text-accent">v{modelVersion}</span>
      </div>
    </div>
  );
}
