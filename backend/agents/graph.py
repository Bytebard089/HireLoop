from langgraph.graph import StateGraph, END
from agents.state import HireLoopState
from agents.nodes.jd_parser      import jd_parser_node
from agents.nodes.resume_scorer  import resume_scorer_node
from agents.nodes.question_gen   import question_gen_node
from agents.nodes.feedback_handler import feedback_handler_node
from agents.nodes.retrainer      import retrainer_node


def _should_retrain(state: HireLoopState) -> str:
    """Conditional edge: only run retrainer if threshold was hit."""
    return "retrainer" if state.get("retrain_triggered") else END


def build_scoring_graph():
    """
    Main pipeline: JD text → ranked candidates + questions.
    Entry: jd_parser → resume_scorer → question_gen → END
    """
    g = StateGraph(HireLoopState)
    g.add_node("jd_parser",     jd_parser_node)
    g.add_node("resume_scorer", resume_scorer_node)
    g.add_node("question_gen",  question_gen_node)

    g.set_entry_point("jd_parser")
    g.add_edge("jd_parser",     "resume_scorer")
    g.add_edge("resume_scorer", "question_gen")
    g.add_edge("question_gen",  END)

    return g.compile()


def build_feedback_graph():
    """
    Feedback loop: store decision → conditionally retrain.
    Entry: feedback_handler → (conditional) retrainer → END
    """
    g = StateGraph(HireLoopState)
    g.add_node("feedback_handler", feedback_handler_node)
    g.add_node("retrainer",        retrainer_node)

    g.set_entry_point("feedback_handler")
    g.add_conditional_edges("feedback_handler", _should_retrain)
    g.add_edge("retrainer", END)

    return g.compile()


# Compiled graphs — import these in API routes
scoring_graph  = build_scoring_graph()
feedback_graph = build_feedback_graph()