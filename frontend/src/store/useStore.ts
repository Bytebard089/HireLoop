import { create } from "zustand";
import type { Candidate, Criteria, Question, ModelImportances } from "../types";

interface HireLoopStore {
  // JD
  jdId: string | null;
  jdText: string;
  criteria: Criteria | null;

  // Candidates
  candidates: Candidate[];
  questions: Record<string, Question[]>;

  // Model
  importances: ModelImportances | null;
  modelVersion: number;
  retrainFlash: boolean;        // triggers UI flash on retrain

  // Actions
  setJD: (jdId: string, jdText: string, criteria: Criteria) => void;
  setCandidates: (candidates: Candidate[], questions: Record<string, Question[]>) => void;
  applyRetrain: (newRanking: Candidate[], importances: Record<string, number>) => void;
  setImportances: (data: ModelImportances) => void;
  updateFeedbackCount: (count: number) => void;
  clearFlash: () => void;
  reset: () => void;
}

// ── Session persistence helpers ────────────────────────────────────────────
const SESSION_KEY = "hireloop_jdId";

function persistJdId(jdId: string | null) {
  if (jdId) {
    sessionStorage.setItem(SESSION_KEY, jdId);
  } else {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

export function getPersistedJdId(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export const useStore = create<HireLoopStore>((set, get) => ({
  jdId: null,
  jdText: "",
  criteria: null,
  candidates: [],
  questions: {},
  importances: null,
  modelVersion: 0,
  retrainFlash: false,

  setJD: (jdId, jdText, criteria) => {
    persistJdId(jdId);
    set({ jdId, jdText, criteria });
  },

  setCandidates: (candidates, questions) =>
    set({ candidates, questions }),

  applyRetrain: (newRanking, importances) => {
    const prev = get().importances;
    const version = (prev?.version ?? 0) + 1;
    // Preserve decision badges from current candidates
    const decisionMap: Record<string, "approve" | "reject"> = {};
    for (const c of get().candidates) {
      if (c.decision) decisionMap[c.candidate_id] = c.decision;
    }
    const merged = newRanking.map((c) => ({
      ...c,
      decision: c.decision ?? decisionMap[c.candidate_id],
    }));
    set((s) => ({
      candidates: merged,
      modelVersion: version,
      retrainFlash: true,
      importances: {
        importances,
        version,
        feedback_count: s.importances?.feedback_count ?? 0,
        history: s.importances?.history ?? [],
      },
    }));
  },

  setImportances: (data) => set({ importances: data, modelVersion: data.version }),

  updateFeedbackCount: (count) =>
    set((s) => ({
      importances: s.importances
        ? { ...s.importances, feedback_count: count }
        : null,
    })),

  clearFlash: () => set({ retrainFlash: false }),

  reset: () => {
    persistJdId(null);
    set({
      jdId: null,
      jdText: "",
      criteria: null,
      candidates: [],
      questions: {},
      importances: null,
      modelVersion: 0,
      retrainFlash: false,
    });
  },
}));
