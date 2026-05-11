"""
Feature engineering for XGBoost scorer.
All features are in [0, 1] range.
"""
import re


def _norm_text(text: str) -> str:
    """Normalize text for robust matching (case/punctuation-insensitive)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _norm_term(term: str) -> str:
    """Normalize a skill/keyword term for robust matching."""
    return _norm_text(term)


# Conceptual phrases that should NOT be treated as matchable skills.
# These are things like "basic ML concepts" which are requirements,
# not discrete technologies.
_CONCEPTUAL_PHRASES = {
    "basic ml concepts", "ml concepts", "basic concepts",
    "good communication", "communication skills", "soft skills",
    "team player", "problem solving", "analytical thinking",
    "strong fundamentals", "cs fundamentals", "basic programming",
    "data structures", "algorithms", "dsa",
}


def _is_conceptual(term: str) -> bool:
    """Check if a term is a conceptual phrase rather than a concrete skill."""
    lower = term.lower().strip()
    if lower in _CONCEPTUAL_PHRASES:
        return True
    # Phrases starting with "basic" + non-tech word are usually conceptual
    if lower.startswith("basic ") and not any(
        tech in lower for tech in ["sql", "python", "java", "html", "css", "react"]
    ):
        return True
    return False


def _split_compound_skill(skill: str) -> list[str]:
    """
    Split compound skills like "NumPy/Pandas" into ["NumPy", "Pandas"].
    Also handles "React or Vue", "Python and SQL", "C/C++", etc.
    """
    original = skill.strip()
    if not original:
        return []

    # Don't split "C/C++" or "CI/CD" — these are single technologies
    compound_exceptions = {"c/c++", "ci/cd", "node.js", "next.js", "vue.js", "react.js"}
    if original.lower() in compound_exceptions:
        return [original]

    # Split on "/" , " or " , " and " , " & "
    parts = re.split(r'\s*/\s*|\s+or\s+|\s+and\s+|\s*&\s*', original)
    parts = [p.strip() for p in parts if p.strip()]

    # If splitting produced the same thing, return as-is
    if len(parts) <= 1:
        return [original]

    return parts


def _has_term(resume_norm: str, term: str) -> bool:
    t = _norm_term(term)
    if not t:
        return False
    return t in resume_norm


def _extract_years(text: str) -> float:
    """
    Parse years-of-experience from resume text.
    Prefers context-anchored patterns (e.g. '3 years of experience')
    over bare occurrences like '5 years ago' to reduce false positives.
    """
    lower = text.lower()

    # 1. Prefer contextually anchored patterns first
    anchored = re.findall(
        r"(\d+)\s*(?:\+)?\s*year[s]?\s+(?:of\s+)?(?:experience|exp|work|software|industry)",
        lower,
    )
    if anchored:
        val = float(anchored[0])
        return val if val <= 50 else 0.0

    # 2. Fallback: any 'N year(s)' that is NOT followed by 'ago'
    fallback = re.findall(
        r"(\d+)\s*(?:\+)?\s*year[s]?(?!\s+ago)",
        lower,
    )
    if fallback:
        val = float(fallback[0])
        return val if val <= 50 else 0.0

    return 0.0


def compute_features(
    resume_text: str,
    criteria: dict,
    semantic_sim: float = 0.0,
) -> dict:
    """
    Returns 4 ML features + supporting metadata for UI display.

    Parameters
    ----------
    resume_text  : raw resume string
    criteria     : {skills, exp_years, level, keywords}
    semantic_sim : pre-computed cross-encoder score from RAG (0-1)

    Returns
    -------
    dict with keys:
        skill_overlap, semantic_sim, exp_gap, keyword_density,
        found_skills, missing_skills, resume_snippet
    """
    # ── Expand compound skills and filter conceptual phrases ──────────────
    raw_skills: list[str] = [str(s).strip() for s in criteria.get("skills", []) if str(s).strip()]
    jd_skills_raw: list[str] = []
    for skill in raw_skills:
        if _is_conceptual(skill):
            continue  # Skip "basic ML concepts" etc.
        expanded = _split_compound_skill(skill)
        jd_skills_raw.extend(expanded)

    # Also expand keywords the same way
    raw_keywords: list[str] = [str(k).strip() for k in criteria.get("keywords", []) if str(k).strip()]
    jd_keywords_raw: list[str] = []
    for kw in raw_keywords:
        expanded = _split_compound_skill(kw)
        jd_keywords_raw.extend(expanded)

    jd_exp:      float     = float(criteria.get("exp_years", 0))

    resume_norm = _norm_text(resume_text)

    # ── skill_overlap: Jaccard on required skills ─────────────────────────────
    if jd_skills_raw:
        found = [s for s in jd_skills_raw if _has_term(resume_norm, s)]
        missing = [s for s in jd_skills_raw if not _has_term(resume_norm, s)]
        skill_overlap = len(found) / len(jd_skills_raw)
    else:
        found, missing = [], []
        skill_overlap  = 0.5   # no info → neutral

    # ── exp_gap: normalised abs difference ───────────────────────────────────
    resume_exp = _extract_years(resume_text)
    if jd_exp > 0:
        exp_gap = min(abs(resume_exp - jd_exp) / 10.0, 1.0)
    else:
        exp_gap = 0.0

    # ── keyword_density: fraction of JD keywords present ────────────────────
    all_terms = jd_skills_raw + jd_keywords_raw
    if all_terms:
        present = sum(1 for t in all_terms if _has_term(resume_norm, t))
        keyword_density = present / len(all_terms)
    else:
        keyword_density = 0.5

    # ── resume snippet for question generation ────────────────────────────────
    # Prefer the experience section over the header (which is usually contact info).
    exp_match = re.search(
        r'\b(experience|work history|employment|professional background)\b(.{50,800})',
        resume_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if exp_match:
        snippet = exp_match.group(2)[:600].replace("\n", " ").strip()
    else:
        snippet = resume_text[:500].replace("\n", " ").strip()

    return {
        "skill_overlap":    round(skill_overlap,    4),
        "semantic_sim":     round(float(semantic_sim), 4),
        "exp_gap":          round(exp_gap,           4),
        "keyword_density":  round(keyword_density,   4),
        # UI helpers
        "found_skills":     found,
        "missing_skills":   missing,
        "resume_years":     resume_exp,
        "resume_snippet":   snippet,
    }
