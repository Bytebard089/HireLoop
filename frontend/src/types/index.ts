export interface Criteria {
  skills:    string[];
  exp_years: number;
  level:     string;
  keywords:  string[];
}

export interface Features {
  skill_overlap:   number;
  semantic_sim:    number;
  exp_gap:         number;
  keyword_density: number;
  found_skills:    string[];
  missing_skills:  string[];
  resume_years:    number;
  resume_snippet:  string;
}

export interface Candidate {
  candidate_id: string;
  name:         string;
  fit_score:    number;
  rank:         number;
  prev_rank:    number;
  rank_change:  number;
  features:     Features;
  decision?:    "approve" | "reject" | null;
}

export interface Question {
  tag:      string;
  question: string;
}

export interface ModelVersion {
  version:        number;
  importances:    Record<string, number>;
  feedback_count: number;
  val_auc:        number | null;
  created_at:     string;
}

export interface ModelImportances {
  importances:    Record<string, number>;
  version:        number;
  feedback_count: number;
  val_auc:        number | null;
  history:        ModelVersion[];
}
