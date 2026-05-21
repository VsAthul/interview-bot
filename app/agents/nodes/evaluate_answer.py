# app/agents/nodes/evaluate_answer.py
import uuid
from datetime import datetime
from app.agents.state import AgentState
from app.models import Conversation
from app.services.groq_service import evaluate_answer


async def evaluate_answer_node(state: AgentState) -> AgentState:
    """
    Node 3 — Evaluates candidate's answer using Groq reflection agent.
    Saves the candidate's answer to DB IMMEDIATELY.
    Adjusts difficulty for the next question based on score.
    """
    db = state["db"]

    # ── Save candidate answer to DB right away ────────────────────────────────
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=state["session_id"],
        interview_id=state["interview_id"],
        speaker="candidate",
        message=state["candidate_answer"],
        question_id=state["current_question_id"],
        timestamp=datetime.utcnow(),
    ))
    await db.commit()

    # Evaluate with Groq
    result = await evaluate_answer(
        question=state["current_question"],
        answer=state["candidate_answer"],
        role=state["candidate"]["role"],
    )

    score = float(result.get("score", 50))

    # Adjust difficulty
    decision = result.get("decision", "maintain_difficulty")
    current  = state["difficulty"]
    if decision == "increase_difficulty":
        new_difficulty = {"easy": "medium", "medium": "hard"}.get(current, "hard")
    elif decision == "decrease_difficulty":
        new_difficulty = {"hard": "medium", "medium": "easy"}.get(current, "easy")
    else:
        new_difficulty = current

    # Append to in-memory conversation for LLM context
    updated_conversation = state["conversation"] + [{
        "question": state["current_question"],
        "answer":   state["candidate_answer"],
    }]

    return {
        **state,
        "scores":       state["scores"] + [score],
        "difficulty":   new_difficulty,
        "conversation": updated_conversation,
    }