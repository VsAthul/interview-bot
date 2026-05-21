# app/agents/nodes/check_completion.py
from app.agents.state import AgentState


async def check_completion(state: AgentState) -> AgentState:
    """
    Node 4 — Decides whether to generate another question or end the interview.
    Simple rule: done when question_number reaches max_questions.
    The LangGraph conditional edge reads state["is_complete"].
    """
    is_done = state["question_number"] >= state["max_questions"]
    return {**state, "is_complete": is_done}