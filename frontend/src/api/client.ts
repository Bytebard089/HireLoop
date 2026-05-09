import type { Candidate, Criteria, FeedbackResponse, ModelImportances, Question } from "../types";

function resolveApiBase(rawBase?: string): string {
  const fallback = "/api";
  if (!rawBase) return fallback;

  const base = rawBase.trim().replace(/\/+$/, "");
  if (!base) return fallback;

  // If user provides full backend origin (e.g. http://localhost:5001),
  // append /api to match backend route prefixes.
  if (/^https?:\/\//i.test(base) && !base.endsWith("/api")) {
    return `${base}/api`;
  }
  return base;
}

const BASE = resolveApiBase(import.meta.env.VITE_API_URL);
console.log("API Base URL:", BASE);

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── JD ─────────────────────────────────────────────────────────────────────

export function parseJD(jdText: string): Promise<{ jd_id: string; criteria: Criteria }> {
  return request("/jd/parse", {
    method: "POST",
    body: JSON.stringify({ jd_text: jdText }),
  });
}

// ── Candidates ──────────────────────────────────────────────────────────────

export function uploadResumes(
  jdId: string,
  resumes: { name: string; text: string }[]
): Promise<{ ranked: Candidate[]; questions: Record<string, Question[]>; criteria: Criteria }> {
  return request("/candidates/upload", {
    method: "POST",
    body: JSON.stringify({ jd_id: jdId, resumes }),
  });
}

export async function uploadResumeFiles(
  jdId: string,
  files: File[]
): Promise<{ ranked: Candidate[]; questions: Record<string, Question[]>; criteria: Criteria }> {
  const form = new FormData();
  form.append("jd_id", jdId);
  for (const file of files) form.append("files", file);

  const res = await fetch(`${BASE}/candidates/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<{ ranked: Candidate[]; questions: Record<string, Question[]>; criteria: Criteria }>;
}

export function listCandidates(jdId: string): Promise<{ candidates: Candidate[] }> {
  return request(`/candidates/?jd_id=${jdId}`);
}

export function getQuestions(candidateId: string, jdId: string): Promise<{ questions: Question[] }> {
  return request(`/candidates/${candidateId}/questions?jd_id=${jdId}`);
}

// ── Feedback ────────────────────────────────────────────────────────────────

export function submitFeedback(
  jdId: string,
  candidateId: string,
  decision: "approve" | "reject"
): Promise<FeedbackResponse> {
  return request("/feedback/", {
    method: "POST",
    body: JSON.stringify({ jd_id: jdId, candidate_id: candidateId, decision }),
  });
}

export function forceRetrain(jdId: string): Promise<{ importances: Record<string, number>; new_ranking: Candidate[] }> {
  return request("/model/retrain", {
    method: "POST",
    body: JSON.stringify({ jd_id: jdId }),
  });
}

export function getImportances(jdId: string): Promise<ModelImportances> {
  return request(`/model/importances/${jdId}`);
}
