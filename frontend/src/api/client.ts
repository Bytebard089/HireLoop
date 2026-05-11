import type {
  Candidate, Criteria, ModelImportances, Question
} from "../types";

export interface FeedbackResponse {
  feedback_count:    number;
  retrain_triggered: boolean;
  importances?:      Record<string, number>;
  new_ranking?:      Candidate[];
}

export interface SkillGap {
  skill:    string;
  severity: string;
  context:  string;
}

export interface QuestionsResponse {
  skill_gaps: SkillGap[];
  questions:  Question[];
}

// ── Base URL ─────────────────────────────────────────────────────────────
function getBase(): string {
  const env = (import.meta as any).env?.VITE_API_URL;
  if (!env) return "/api";
  const b = env.trim().replace(/\/+$/, "");
  return b.endsWith("/api") ? b : `${b}/api`;
}
const BASE = getBase();

// ── Cold-start detection ─────────────────────────────────────────────────
let _backendAwake = false;
const COLD_START_THRESHOLD_MS = 5000;

/**
 * Proactively wake the backend on page load.
 * Returns true if backend responded quickly (already warm).
 */
export async function warmUpBackend(): Promise<boolean> {
  if (_backendAwake) return true;
  try {
    const start = Date.now();
    const res = await fetch(`${BASE.replace('/api', '')}/health`, {
      signal: AbortSignal.timeout(60_000),
    });
    const elapsed = Date.now() - start;
    _backendAwake = res.ok;
    return elapsed < COLD_START_THRESHOLD_MS;
  } catch {
    return false;
  }
}

// ── Generic fetch helper with cold-start awareness ────────────────────────
type ProgressCallback = (stage: "connecting" | "waking" | "processing") => void;

async function req<T>(
  path: string,
  options?: RequestInit,
  onProgress?: ProgressCallback,
): Promise<T> {
  const isForm = options?.body instanceof FormData;

  // Notify caller of connection attempt
  onProgress?.("connecting");

  // Start a timer to detect cold-start
  let wakingTimeout: ReturnType<typeof setTimeout> | undefined;
  if (!_backendAwake && onProgress) {
    wakingTimeout = setTimeout(() => {
      onProgress("waking");
    }, COLD_START_THRESHOLD_MS);
  }

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: !isForm ? { "Content-Type": "application/json" } : {},
      ...options,
    });

    // Backend is now confirmed awake
    _backendAwake = true;
    if (wakingTimeout) clearTimeout(wakingTimeout);
    onProgress?.("processing");

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err?.error ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if (wakingTimeout) clearTimeout(wakingTimeout);
    throw e;
  }
}

// ── JD ────────────────────────────────────────────────────────────────────
export function parseJD(
  jdText: string,
  onProgress?: ProgressCallback,
): Promise<{ jd_id: string; criteria: Criteria }> {
  return req("/jd/parse", { method: "POST", body: JSON.stringify({ jd_text: jdText }) }, onProgress);
}

// ── Candidates ────────────────────────────────────────────────────────────
export async function uploadResumeFiles(
  jdId: string,
  files: File[],
  onProgress?: ProgressCallback,
): Promise<{ ranked: Candidate[]; questions: Record<string, any>; jd_id: string }> {
  const form = new FormData();
  form.append("jd_id", jdId);
  files.forEach(f => form.append("files", f));
  return req("/candidates/upload", { method: "POST", body: form }, onProgress);
}

export function listCandidates(jdId: string): Promise<{ candidates: Candidate[] }> {
  return req(`/candidates/?jd_id=${encodeURIComponent(jdId)}`);
}

export function getQuestions(
  candidateId: string, jdId: string
): Promise<QuestionsResponse> {
  return req(`/candidates/${candidateId}/questions?jd_id=${encodeURIComponent(jdId)}`);
}

// ── Feedback ──────────────────────────────────────────────────────────────
export function submitFeedback(
  jdId: string, candidateId: string, decision: "approve" | "reject"
): Promise<FeedbackResponse> {
  return req("/feedback/", {
    method: "POST",
    body: JSON.stringify({ jd_id: jdId, candidate_id: candidateId, decision }),
  });
}

export function forceRetrain(
  jdId: string
): Promise<{ importances: Record<string, number>; new_ranking: Candidate[] }> {
  return req("/model/retrain", { method: "POST", body: JSON.stringify({ jd_id: jdId }) });
}

// ── Model ─────────────────────────────────────────────────────────────────
export function getImportances(jdId: string): Promise<ModelImportances> {
  return req(`/model/importances/${encodeURIComponent(jdId)}`);
}

// ── Export ────────────────────────────────────────────────────────────────
export function exportShortlist(jdId: string): Promise<Blob> {
  return fetch(`${BASE}/candidates/export?jd_id=${encodeURIComponent(jdId)}`)
    .then(r => r.blob());
}
