from typing import TypedDict, Optional


class HireLoopState(TypedDict):
    # Set at entry
    jd_text:      str
    jd_id:        str

    # Populated by jd_parser
    criteria:     dict          # {skills, exp_years, level, keywords}

    # Populated by resume_scorer
    resumes:      list[dict]    # raw resume dicts from DB
    ranked:       list[dict]    # [{candidate_id, name, score, rank, prev_rank, features}]

    # Populated by question_gen
    questions:    dict          # {candidate_id: [str, str, str]}

    # Populated by feedback_handler
    feedback_buf: list[dict]    # [{candidate_id, label, features}]
    retrain_triggered: bool

    # Populated by retrainer
    importances:  dict          # {feature_name: weight}
    new_ranked:   list[dict]    # re-ranked after retrain