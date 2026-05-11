import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { parseJD, uploadResumeFiles, warmUpBackend } from "../api/client";
import { useStore } from "../store/useStore";

const DEMO_JD = `Senior Frontend Engineer — Remote

We're looking for a senior engineer with 3+ years of React and TypeScript. 
You'll own our design system, ship accessible (WCAG 2.1) components, 
and work with GraphQL APIs. Experience with performance optimisation 
and Core Web Vitals is strongly preferred.

Required: React, TypeScript, GraphQL
Nice to have: accessibility, performance, testing`;

const LOADING_MESSAGES = {
  connecting: "Connecting to server...",
  waking: "Backend is waking up (~30s)...",
  processing: "Parsing job description...",
  scoring: "Scoring resumes with AI...",
  scoring_waking: "Backend is waking up (~30s)...",
};

export default function JDInput() {
  const [jdText,   setJdText]   = useState("");
  const [step,     setStep]     = useState<"jd" | "resumes">("jd");
  const [jdId,     setJdId]     = useState("");
  const [criteria, setCriteria] = useState<any>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error,    setError]    = useState<string | null>(null);
  const [backendReady, setBackendReady] = useState<boolean | null>(null);
  const fileRef  = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const store    = useStore();

  // Proactively warm up the backend on component mount
  useEffect(() => {
    warmUpBackend().then(wasWarm => {
      setBackendReady(true);
      if (!wasWarm) {
        console.log("[HireLoop] Backend cold-started successfully");
      }
    }).catch(() => {
      setBackendReady(false);
    });
  }, []);

  async function handleParseJD() {
    if (!jdText.trim()) return;
    setLoading(true); setError(null);
    setLoadingMsg(LOADING_MESSAGES.connecting);
    try {
      const res = await parseJD(jdText, (stage) => {
        if (stage === "waking") setLoadingMsg(LOADING_MESSAGES.waking);
        else if (stage === "processing") setLoadingMsg(LOADING_MESSAGES.processing);
      });
      setJdId(res.jd_id);
      setCriteria(res.criteria);
      store.setJD(res.jd_id, jdText, res.criteria);
      setStep("resumes");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    setFiles((prev) => [...prev, ...Array.from(files)]);
  }

  async function handleScore() {
    if (!files.length) return;
    setLoading(true); setError(null);
    setLoadingMsg("Scoring resumes with AI...");
    try {
      const res = await uploadResumeFiles(jdId, files, (stage) => {
        if (stage === "waking") setLoadingMsg(LOADING_MESSAGES.scoring_waking);
        else if (stage === "processing") setLoadingMsg("AI is analyzing resumes...");
      });
      store.setCandidates(res.ranked, res.questions);
      navigate("/dashboard");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  return (
    <div className="page-jdinput">
      {step === "jd" ? (
        <div className="jdinput-card">
          <div className="step-indicator">
            <span className="step active">1 JD</span>
            <span className="step-sep">→</span>
            <span className="step">2 Resumes</span>
            <span className="step-sep">→</span>
            <span className="step">3 Dashboard</span>
          </div>

          <h2 className="card-title">Paste a Job Description</h2>
          <p className="card-sub">The agent will extract weighted criteria in seconds.</p>

          <textarea
            className="jd-textarea"
            placeholder="Paste JD here…"
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={10}
          />

          <div className="jdinput-actions">
            <button
              className="btn-ghost"
              onClick={() => setJdText(DEMO_JD)}
              type="button"
            >
              Use demo JD
            </button>
            <button
              className="btn-primary"
              onClick={handleParseJD}
              disabled={!jdText.trim() || loading}
            >
              {loading ? (
                <span className="loading-state">
                  <span className="spinner" />
                  {loadingMsg || "Parsing…"}
                </span>
              ) : "Parse JD →"}
            </button>
          </div>

          {/* Cold-start warning banner */}
          {loading && loadingMsg.includes("waking") && (
            <div className="cold-start-banner">
              <span className="cold-start-icon">☕</span>
              <div>
                <strong>Backend is waking up</strong>
                <p>Free-tier servers spin down after inactivity. This typically takes 30–60 seconds on the first request.</p>
              </div>
            </div>
          )}

          {error && <p className="error-msg">{error}</p>}
        </div>
      ) : (
        <div className="jdinput-card">
          <div className="step-indicator">
            <span className="step done">1 JD ✓</span>
            <span className="step-sep">→</span>
            <span className="step active">2 Resumes</span>
            <span className="step-sep">→</span>
            <span className="step">3 Dashboard</span>
          </div>

          <div className="criteria-preview">
            <h4>Extracted criteria</h4>
            <div className="criteria-chips">
              {criteria?.skills?.map((s: string) => (
                <span key={s} className="chip chip-found">{s}</span>
              ))}
              {criteria?.keywords?.map((k: string) => (
                <span key={k} className="chip chip-keyword">{k}</span>
              ))}
              <span className="chip chip-meta">{criteria?.exp_years}yr+ · {criteria?.level}</span>
            </div>
          </div>

          <h2 className="card-title">Upload Resumes</h2>
          <p className="card-sub">Upload .txt or .pdf files — one per candidate.</p>

          <div
            className="dropzone"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
          >
            {files.length === 0
              ? <span>Drop .txt/.pdf resume files here or click to browse</span>
              : (
                <ul className="resume-list">
                  {files.map((f, i) => (
                    <li key={i} className="resume-item">
                      <span className="resume-icon">📄</span>
                      <span>{f.name}</span>
                      <button
                        className="resume-remove"
                        onClick={(e) => { e.stopPropagation(); setFiles(curr => curr.filter((_, j) => j !== i)); }}
                      >✕</button>
                    </li>
                  ))}
                </ul>
              )
            }
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".txt,.pdf"
              style={{ display: "none" }}
              onChange={(e) => handleFiles(e.target.files)}
            />
          </div>

          <div className="jdinput-actions">
            <button className="btn-ghost" onClick={() => setStep("jd")}>← Back</button>
            <button
              className="btn-primary"
              onClick={handleScore}
              disabled={!files.length || loading}
            >
              {loading ? (
                <span className="loading-state">
                  <span className="spinner" />
                  {loadingMsg || "Scoring…"}
                </span>
              ) : `Score ${files.length} Resume${files.length !== 1 ? "s" : ""} →`}
            </button>
          </div>

          {/* Cold-start warning banner */}
          {loading && loadingMsg.includes("waking") && (
            <div className="cold-start-banner">
              <span className="cold-start-icon">☕</span>
              <div>
                <strong>Backend is waking up</strong>
                <p>Free-tier servers spin down after inactivity. This typically takes 30–60 seconds on the first request.</p>
              </div>
            </div>
          )}

          {error && <p className="error-msg">{error}</p>}
        </div>
      )}
    </div>
  );
}
