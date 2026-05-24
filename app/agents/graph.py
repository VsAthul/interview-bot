# app/agents/graph.py

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState

from app.agents.nodes.load_candidate import load_candidate
from app.agents.nodes.generate_question import generate_question
from app.agents.nodes.evaluate_answer import evaluate_answer_node
from app.agents.nodes.check_completion import check_completion
from app.agents.nodes.generate_report import generate_report


# =====================================================
# ENTRY ROUTER
# =====================================================


def route_phase(state: AgentState) -> str:
    """
    Routes graph execution based on workflow phase.

    start  -> load candidate + generate first question
    answer -> evaluate answer workflow
    report -> generate final report
    """

    phase = state["phase"]

    if phase == "start":
        return "load_candidate"

    elif phase == "answer":
        return "evaluate_answer"

    elif phase == "report":
        return "generate_report"

    raise ValueError(f"Invalid phase: {phase}")


# =====================================================
# POST COMPLETION ROUTER
# =====================================================


def route_after_completion(state: AgentState) -> str:
    """
    Determines next step after answer evaluation.
    """

    if state.get("error"):
        return END

    return (
        "generate_report"
        if state["is_complete"]
        else "generate_question"
    )


# =====================================================
# BUILD GRAPH
# =====================================================


def build_interview_graph():
    g = StateGraph(AgentState)

    # =================================================
    # NODES
    # =================================================

    g.add_node("load_candidate", load_candidate)
    g.add_node("generate_question", generate_question)
    g.add_node("evaluate_answer", evaluate_answer_node)
    g.add_node("check_completion", check_completion)
    g.add_node("generate_report", generate_report)

    # =================================================
    # ENTRY ROUTING
    # =================================================

    g.set_conditional_entry_point(
        route_phase,
        {
            "load_candidate": "load_candidate",
            "evaluate_answer": "evaluate_answer",
            "generate_report": "generate_report",
        },
    )

    # =================================================
    # START FLOW
    # =================================================

    g.add_edge("load_candidate", "generate_question")
    g.add_edge("generate_question", END)

    # =================================================
    # ANSWER FLOW
    # =================================================

    g.add_edge("evaluate_answer", "check_completion")

    g.add_conditional_edges(
        "check_completion",
        route_after_completion,
        {
            "generate_question": "generate_question",
            "generate_report": "generate_report",
        },
    )

    # =================================================
    # TERMINAL STATES
    # =================================================

    g.add_edge("generate_report", END)

    return g.compile()


# Singleton compiled graph
interview_graph = build_interview_graph()