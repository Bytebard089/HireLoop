"""
Unit tests for HireLoop backend.
Run: pytest tests/ -v
"""
import pytest
import sys
import os

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ml.features import compute_features, _extract_years, _norm_text


# ─────────────────────────────────────────────────────────────────────────────
# _norm_text
# ─────────────────────────────────────────────────────────────────────────────

def test_norm_text_lowercases():
    assert _norm_text("React TypeScript") == "reacttypescript"


def test_norm_text_strips_punctuation():
    assert _norm_text("C++, Node.js") == "cnodejs"


# ─────────────────────────────────────────────────────────────────────────────
# _extract_years
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_years_basic():
    assert _extract_years("5 years of experience in Python") == 5.0


def test_extract_years_plus():
    assert _extract_years("3+ years of experience") == 3.0


def test_extract_years_ignores_ago():
    # "5 years ago" should not be picked up as years of experience
    text = "5 years ago I switched careers. Now I have 2 years of software experience."
    assert _extract_years(text) == 2.0


def test_extract_years_no_mention():
    assert _extract_years("Software engineer skilled in Python") == 0.0


def test_extract_years_outlier_clamped():
    # 99 years is impossible experience — should return 0
    assert _extract_years("99 years of experience") == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_features — skill_overlap
# ─────────────────────────────────────────────────────────────────────────────

CRITERIA_FRONTEND = {
    "skills":    ["React", "TypeScript", "GraphQL"],
    "exp_years": 3,
    "keywords":  ["accessibility", "performance"],
}


def test_skill_overlap_full_match():
    resume = "React TypeScript GraphQL developer with 3 years of experience"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    assert feats["skill_overlap"] == 1.0


def test_skill_overlap_partial_match():
    resume = "React developer, 2 years of experience. No GraphQL."
    feats = compute_features(resume, CRITERIA_FRONTEND)
    # React and TypeScript missing TypeScript → 1/3 or 2/3 depending on resume
    assert 0.0 < feats["skill_overlap"] < 1.0


def test_skill_overlap_no_match():
    resume = "Java Spring Boot backend developer"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    assert feats["skill_overlap"] == 0.0


def test_skill_overlap_case_insensitive():
    resume = "react typescript graphql"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    assert feats["skill_overlap"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_features — exp_gap
# ─────────────────────────────────────────────────────────────────────────────

def test_exp_gap_exact_match():
    resume = "3 years of experience in frontend"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    # abs(3-3)/10 = 0.0
    assert feats["exp_gap"] == 0.0


def test_exp_gap_overqualified():
    resume = "8 years of experience in React TypeScript"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    # abs(8-3)/10 = 0.5
    assert feats["exp_gap"] == pytest.approx(0.5, abs=0.01)


def test_exp_gap_underqualified():
    resume = "1 year of experience in React"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    # abs(1-3)/10 = 0.2
    assert feats["exp_gap"] == pytest.approx(0.2, abs=0.01)


def test_exp_gap_clamped_at_1():
    resume = "0 years of experience"
    criteria = {"skills": [], "exp_years": 15, "keywords": []}
    feats = compute_features("junior developer", criteria)
    assert feats["exp_gap"] <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_features — keyword_density
# ─────────────────────────────────────────────────────────────────────────────

def test_keyword_density_all_present():
    resume = "Expert in accessibility and performance optimization"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    # Both keywords present + 0 skills matched → density = 2/(3+2) = 0.4... wait
    # skills: react, typescript, graphql all missing + keywords: accessibility, performance both present
    # total terms = 5, present = 2
    assert feats["keyword_density"] == pytest.approx(2 / 5, abs=0.01)


def test_keyword_density_none_present():
    resume = "Java Spring Boot microservices developer"
    feats = compute_features(resume, CRITERIA_FRONTEND)
    assert feats["keyword_density"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_features — empty criteria edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_criteria_returns_neutral():
    feats = compute_features("Some resume text", {})
    assert feats["skill_overlap"]   == 0.5   # neutral fallback
    assert feats["keyword_density"] == 0.5   # neutral fallback
    assert feats["exp_gap"]         == 0.0   # no jd_exp → gap = 0


def test_semantic_sim_passed_through():
    feats = compute_features("Some resume", {}, semantic_sim=0.75)
    assert feats["semantic_sim"] == pytest.approx(0.75)


# ─────────────────────────────────────────────────────────────────────────────
# compute_features — found/missing skill lists
# ─────────────────────────────────────────────────────────────────────────────

def test_found_and_missing_skills_correct():
    resume = "React and TypeScript developer. No backend experience."
    feats = compute_features(resume, CRITERIA_FRONTEND)
    assert "React" in feats["found_skills"]
    assert "TypeScript" in feats["found_skills"]
    assert "GraphQL" in feats["missing_skills"]


def test_features_all_in_0_1_range():
    resume = "Senior React TypeScript engineer with 4 years of experience in GraphQL and accessibility"
    feats = compute_features(resume, CRITERIA_FRONTEND, semantic_sim=0.8)
    for key in ["skill_overlap", "semantic_sim", "exp_gap", "keyword_density"]:
        assert 0.0 <= feats[key] <= 1.0, f"{key} out of range: {feats[key]}"
