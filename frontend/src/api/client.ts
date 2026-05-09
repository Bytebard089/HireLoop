import type {
  Candidate, Criteria, ModelImportances, Question
} from "../types";

export interface FeedbackResponse {
  feedback_count:    number;
  retrain_triggered: boolean;
  importances?:      Record<string, number>;
  new_ranking?:      Candidate[];
}

// ── Base URL ─────────────────────────────────────────────────────────────
function getBase(): string {
  const env = (import.meta as any).env?.VITE_API_URL;
  if (!env) return "/api";
  const b = env.trim().replace(/\/+$/, "");
  return b.endsWith("/api") ? b : `${b}/api`;
}
const BASE = getBase();

// ── Generic fetch helper ──────────────────────────────────────────────────
async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const isForm = options?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    headers: !isForm ? { "Content-Type": "application/json" } : {},
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err?.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── JD ────────────────────────────────────────────────────────────────────
export function parseJD(jdText: string): Promise<{ jd_id: string; criteria: Criteria }> {
  return req("/jd/parse", { method: "POST", body: JSON.stringify({ jd_text: jdText }) });
}

// ── Candidates ────────────────────────────────────────────────────────────
export async function uploadResumeFiles(
  jdId: string, files: File[]
): Promise<{ ranked: Candidate[]; questions: Record<string, Question[]>; jd_id: string }> {
  const form = new FormData();
  form.append("jd_id", jdId);
  files.forEach(f => form.append("files", f));
  return req("/candidates/upload", { method: "POST", body: form });
}

export function listCandidates(jdId: string): Promise<{ candidates: Candidate[] }> {
  return req(`/candidates/?jd_id=${encodeURIComponent(jdId)}`);
}

export function getQuestions(
  candidateId: string, jdId: string
): Promise<{ questions: Question[] }> {
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
