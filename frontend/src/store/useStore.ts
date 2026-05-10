import { create } from "zustand";
import toast from "react-hot-toast";
import type { Candidate, Criteria, ModelImportances } from "../types";

// ── Session persistence (fixes page-refresh bug) ──────────────────────────
const SESSION_KEY = "hireloop_jd_id";
export function getPersistedJdId(): string | null {
  try { return sessionStorage.getItem(SESSION_KEY); } catch { return null; }
}
function persistJdId(id: string) {
  try { sessionStorage.setItem(SESSION_KEY, id); } catch {}
}
function clearPersistedJdId() {
  try { sessionStorage.removeItem(SESSION_KEY); } catch {}
}

interface HireLoopStore {
  jdId:          string | null;
  jdText:        string;
  criteria:      Criteria | null;
  candidates:    Candidate[];
  questions:     Record<string, import("../types").Question[]>;
  importances:   ModelImportances | null;
  modelVersion:  number;
  retrainFlash:  boolean;

  setJD:              (id: string, text: string, criteria: Criteria) => void;
  setCandidates:      (candidates: Candidate[], questions: Record<string, import("../types").Question[]>) => void;
  updateDecision:     (candidateId: string, decision: "approve" | "reject") => void;

  // ── FIXED: merges decisions back in so badges survive retrain ──────────
  applyRetrain:       (newRanking: Candidate[], importances: Record<string, number>) => void;

  setImportances:     (data: ModelImportances) => void;
  updateFeedbackCount:(count: number) => void;
  clearFlash:         () => void;
  reset:              () => void;
}

export const useStore = create<HireLoopStore>((set, get) => ({
  jdId:         null,
  jdText:       "",
  criteria:     null,
  candidates:   [],
  questions:    {},
  importances:  null,
  modelVersion: 0,
  retrainFlash: false,

  setJD: (jdId, jdText, criteria) => {
    persistJdId(jdId);
    set({ jdId, jdText, criteria });
  },

  setCandidates: (candidates, questions) =>
    set({ candidates, questions }),

  // Optimistic local update before API round-trip
  updateDecision: (candidateId, decision) =>
    set(s => ({
      candidates: s.candidates.map(c =>
        c.candidate_id === candidateId ? { ...c, decision } : c
      )
    })),

  // ── THE KEY FIX: ──────────────────────────────────────────────────────
  // 1. Build a decisionMap from the CURRENT candidates before replacing them
  // 2. Merge backend's new_ranking with those decisions
  // 3. This ensures approved/rejected badges persist across retrains
  applyRetrain: (newRanking, importances) => {
    const { candidates: current, importances: imp } = get();

    // Snapshot current decisions
    const decisionMap: Record<string, "approve" | "reject"> = {};
    current.forEach(c => { if (c.decision) decisionMap[c.candidate_id] = c.decision; });

    // Merge: backend may already send decisions (from retrainer.py fix),
    // but fall back to local snapshot in case of mismatch
    const merged = newRanking.map(c => ({
      ...c,
      decision: c.decision ?? decisionMap[c.candidate_id] ?? null,
    }));

    const newVersion = (imp?.version ?? 0) + 1;
    
    // Trigger toast notification
    toast(`✨ Model Retrained: v${newVersion}`, {
      icon: '🧠',
      style: {
        borderRadius: '10px',
        background: 'rgba(255, 255, 255, 0.85)',
        color: 'var(--text-primary)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid var(--border)',
        fontSize: '13px',
        fontWeight: 600,
        boxShadow: 'var(--shadow-md)'
      },
    });

    set(s => ({
      candidates:   merged,
      modelVersion: newVersion,
      retrainFlash: true,
      importances: s.importances ? {
        ...s.importances,
        importances,
        version:       newVersion,
        history: [
          ...(s.importances.history ?? []),
          {
            version:        newVersion,
            importances,
            feedback_count: s.importances.feedback_count ?? 0,
            val_auc:        null,
            created_at:     new Date().toISOString(),
          }
        ],
      } : null,
    }));
  },

  setImportances: (data) =>
    set({ importances: data, modelVersion: data.version }),

  updateFeedbackCount: (count) =>
    set(s => ({
      importances: s.importances
        ? { ...s.importances, feedback_count: count }
        : null,
    })),

  clearFlash: () => set({ retrainFlash: false }),

  reset: () => {
    clearPersistedJdId();
    set({
      jdId: null, jdText: "", criteria: null,
      candidates: [], questions: {}, importances: null,
      modelVersion: 0, retrainFlash: false,
    });
  },
}));
