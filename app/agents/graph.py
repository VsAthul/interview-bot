# app/agents/graph.py
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes.load_candidate   import load_candidate
from app.agents.nodes.generate_question import generate_question
from app.agents.nodes.evaluate_answer  import evaluate_answer_node
from app.agents.nodes.check_completion import check_completion
from app.agents.nodes.generate_report  import generate_report


def _route(state: AgentState) -> str:
    """Conditional edge: loop back or finish."""
    return "generate_report" if state["is_complete"] else "generate_question"


def build_graph():
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("load_candidate",    load_candidate)
    g.add_node("generate_question", generate_question)
    g.add_node("evaluate_answer",   evaluate_answer_node)
    g.add_node("check_completion",  check_completion)
    g.add_node("generate_report",   generate_report)

    # Entry point
    g.set_entry_point("load_candidate")

    # Linear edges
    g.add_edge("load_candidate",    "generate_question")
    g.add_edge("generate_question", "evaluate_answer")
    g.add_edge("evaluate_answer",   "check_completion")

    # Conditional: loop or end
    g.add_conditional_edges("check_completion", _route, {
        "generate_question": "generate_question",
        "generate_report":   "generate_report",
    })

    g.add_edge("generate_report", END)
    return g.compile()


# Single compiled instance — import this everywhere
interview_graph = build_graph()