# app/agents/nodes/evaluate_answer.py

import uuid
from datetime import datetime

from app.agents.state import AgentState
from app.models import Conversation
from app.services.groq_service import evaluate_answer


async def evaluate_answer_node(state: AgentState) -> AgentState:
    """
    Evaluates candidate answer.

    Responsibilities:
    - Persist candidate response
    - Evaluate answer using LLM
    - Adjust difficulty
    - Update in-memory interview state
    """

    db = state["db"]

    # =====================================================================
    # SAVE CANDIDATE ANSWER
    # =====================================================================

    db.add(
        Conversation(
            conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
            session_id=state["session_id"],
            interview_id=state["interview_id"],
            speaker="candidate",
            message=state["candidate_answer"],
            question_id=state["current_question_id"],
            timestamp=datetime.utcnow(),
        )
    )

    await db.commit()

    # =====================================================================
    # EVALUATE ANSWER
    # =====================================================================

    try:

        result = await evaluate_answer(
            question=state["current_question"],
            answer=state["candidate_answer"],
            role=state["candidate"]["role"],
        )

        try:
            score = float(result.get("score", 50))
        except (TypeError, ValueError):
            score = 50.0

        # ================================================================
        # ADAPTIVE DIFFICULTY
        # ================================================================

        decision = result.get(
            "decision",
            "maintain_difficulty",
        )

        current = state["difficulty"]

        if decision == "increase_difficulty":

            new_difficulty = {
                "easy": "medium",
                "medium": "hard",
            }.get(current, "hard")

        elif decision == "decrease_difficulty":

            new_difficulty = {
                "hard": "medium",
                "medium": "easy",
            }.get(current, "easy")

        else:
            new_difficulty = current

    except Exception as e:

        # Safe fallback
        score = 50.0
        new_difficulty = state["difficulty"]

        state["error"] = str(e)

    # =====================================================================
    # UPDATE MEMORY STATE
    # =====================================================================

    updated_conversation = state["conversation"] + [
        {
            "question": state["current_question"],
            "answer": state["candidate_answer"],
        }
    ]

    state["scores"] = state["scores"] + [score]
    state["difficulty"] = new_difficulty
    state["conversation"] = updated_conversation

    return state