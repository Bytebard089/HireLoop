from db.models import Feedback, Candidate, get_session
from agents.state import HireLoopState


RETRAIN_THRESHOLD = 5   # retrain every N feedback decisions


def feedback_handler_node(state: HireLoopState) -> HireLoopState:
    """
    Writes a single feedback decision to DB.
    Buffers the feature vector + label.
    Triggers retrainer if feedback_count % RETRAIN_THRESHOLD == 0.
    """
    buf = state.get("feedback_buf", [])

    with get_session() as session:
        # Count total feedback for this JD
        from sqlalchemy import func, select
        count_q = select(func.count()).select_from(Feedback).where(
            Feedback.jd_id == state["jd_id"]
        )
        feedback_count = session.execute(count_q).scalar()

    retrain_triggered = (feedback_count > 0) and (feedback_count % RETRAIN_THRESHOLD == 0)

    return {
        **state,
        "feedback_buf":      buf,
        "retrain_triggered": retrain_triggered,
    }