# app/agents/nodes/evaluate_answer.py

import uuid
from datetime import datetime

from app.agents.state import AgentState
from app.models import Conversation
from app.services.groq_service import evaluate_answer
from langchain_core.runnables import RunnableConfig

# ============================================================================
# BLOOM TAXONOMY ORDER
# ============================================================================

BLOOM_ORDER = [
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
]


# ============================================================================
# EVALUATE ANSWER NODE
# ============================================================================

async def evaluate_answer_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Evaluates candidate answer.

    Responsibilities:
    - Persist candidate response
    - Evaluate answer using LLM
    - Adjust difficulty
    - Adjust Bloom's taxonomy level
    - Update interview memory state
    """

    db = config["configurable"]["db"]

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
    # DEFAULT FALLBACKS
    # =====================================================================

    score        = 50.0
    new_difficulty = state["difficulty"]
    current_bloom  = state.get("bloom_level", "understand")
    new_bloom      = current_bloom
    feedback       = ""
    error: str | None = None          # ← captured locally, never written to state

    # =====================================================================
    # EVALUATE ANSWER USING LLM
    # =====================================================================

    try:

        result = await evaluate_answer(
            question=state["current_question"],
            answer=state["candidate_answer"],
            role=state["candidate"]["role"],
        )

        # ================================================================
        # SCORE
        # ================================================================

        try:
            score = float(result.get("score", 50))
        except (TypeError, ValueError):
            score = 50.0

        feedback = result.get("feedback", "")

        # ================================================================
        # ADAPTIVE DIFFICULTY
        # ================================================================

        decision = result.get("decision", "maintain_difficulty")
        current  = state["difficulty"]

        if decision == "increase_difficulty":
            new_difficulty = {"easy": "medium", "medium": "hard"}.get(current, "hard")

        elif decision == "decrease_difficulty":
            new_difficulty = {"hard": "medium", "medium": "easy"}.get(current, "easy")

        else:
            new_difficulty = current

        # ================================================================
        # BLOOM TAXONOMY ADAPTATION
        # ================================================================

        idx = BLOOM_ORDER.index(current_bloom)

        if score >= 85 and idx < len(BLOOM_ORDER) - 1:
            new_bloom = BLOOM_ORDER[idx + 1]

        elif score < 50 and idx > 0:
            new_bloom = BLOOM_ORDER[idx - 1]

        else:
            new_bloom = current_bloom

    except Exception as e:
        error = str(e)                # ← local var, not state mutation

    # =====================================================================
    # UPDATE MEMORY STATE — return new dict, never mutate state
    # =====================================================================

    updated_conversation = state["conversation"] + [
        {
            "question":    state["current_question"],
            "answer":      state["candidate_answer"],
            "score":       score,
            "feedback":    feedback,
            "difficulty":  new_difficulty,
            "bloom_level": new_bloom,
        }
    ]

    return {
        **state,
        "scores":       state["scores"] + [score],
        "difficulty":   new_difficulty,
        "bloom_level":  new_bloom,
        "conversation": updated_conversation,
        "error":        error,        # None on success, str on failure
    }