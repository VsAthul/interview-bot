# app/agents/graph.py
"""
Two separate graphs replacing the single looping graph.

WHY TWO GRAPHS?
───────────────
The original graph ran load_candidate → generate_question → evaluate_answer
→ check_completion → (loop or end) in one shot. This is fine for a fully
autonomous agent, but our interview is human-in-the-loop: the frontend
drives each turn (mic → STT → submit). We can't block an HTTP request
waiting for the candidate to speak.

Solution: split at the human turn boundary.

  start_graph   — runs once at interview start
    load_candidate → generate_question → END
    Returns the first question. Pauses. Waits for candidate.

  answer_graph  — runs once per answer submission
    evaluate_answer → check_completion → generate_question  (if more)
                                      → generate_report     (if done)
    Resumes from saved AgentState. Returns next question or final report.

AgentState is persisted to session.agent_state (JSON) in DB between calls.
The `db` key is stripped before saving and re-injected on restore.
"""

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes.load_candidate    import load_candidate
from app.agents.nodes.generate_question import generate_question
from app.agents.nodes.evaluate_answer   import evaluate_answer_node
from app.agents.nodes.check_completion  import check_completion
from app.agents.nodes.generate_report   import generate_report


def _route(state: AgentState) -> str:
    """Conditional edge after check_completion."""
    return "generate_report" if state["is_complete"] else "generate_question"


def build_start_graph():
    """
    Graph for /start endpoint.
    load_candidate → generate_question → END
    """
    g = StateGraph(AgentState)

    g.add_node("load_candidate",    load_candidate)
    g.add_node("generate_question", generate_question)

    g.set_entry_point("load_candidate")
    g.add_edge("load_candidate",    "generate_question")
    g.add_edge("generate_question", END)

    return g.compile()


def build_answer_graph():
    """
    Graph for /submit-answer endpoint.
    evaluate_answer → check_completion → generate_question (loop)
                                      OR generate_report   (done)
    """
    g = StateGraph(AgentState)

    g.add_node("evaluate_answer",  evaluate_answer_node)
    g.add_node("check_completion", check_completion)
    g.add_node("generate_question", generate_question)
    g.add_node("generate_report",  generate_report)

    g.set_entry_point("evaluate_answer")
    g.add_edge("evaluate_answer",  "check_completion")

    g.add_conditional_edges("check_completion", _route, {
        "generate_question": "generate_question",
        "generate_report":   "generate_report",
    })

    g.add_edge("generate_question", END)
    g.add_edge("generate_report",   END)

    return g.compile()


def build_report_graph():
    """
    Graph for /end endpoint (early exit).
    generate_report → END
    """
    g = StateGraph(AgentState)
    g.add_node("generate_report", generate_report)
    g.set_entry_point("generate_report")
    g.add_edge("generate_report", END)
    return g.compile()


# Compiled instances — import these in routers
start_graph  = build_start_graph()
answer_graph = build_answer_graph()
report_graph = build_report_graph()