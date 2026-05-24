# app/agents/nodes/generate_question.py

import uuid
from datetime import datetime

from app.agents.state import AgentState
from app.models import Conversation
from app.services.groq_service import generate_interview_question


# ============================================================================
# BLOOM'S TAXONOMY HELPERS
# ============================================================================

BLOOM_DESCRIPTIONS = {

    "remember":
        "Ask recall-based questions about definitions, concepts, or facts.",

    "understand":
        "Ask conceptual explanation questions to test understanding.",

    "apply":
        "Ask scenario-based questions where concepts must be applied.",

    "analyze":
        "Ask comparison, debugging, optimization, or reasoning questions.",

    "evaluate":
        "Ask judgment, tradeoff, architecture, or decision-making questions.",

    "create":
        "Ask system design or solution creation questions.",
}


# ============================================================================
# GENERATE QUESTION NODE
# ============================================================================

async def generate_question(state: AgentState) -> AgentState:
    """
    Generates next interview question.

    Responsibilities:
    - Uses adaptive difficulty
    - Uses Bloom's Taxonomy cognitive level
    - Persists generated question
    """

    c = state["candidate"]

    bloom_level = state.get(
        "bloom_level",
        "understand",
    )

    bloom_instruction = BLOOM_DESCRIPTIONS.get(
        bloom_level,
        BLOOM_DESCRIPTIONS["understand"],
    )

    # =====================================================================
    # GENERATE QUESTION USING LLM
    # =====================================================================

    result = await generate_interview_question(
        role=c["role"],
        experience=c["experience"],
        skillset=c["skillset"],
        previous_qa=state["conversation"],
        difficulty=state["difficulty"],

        # NEW
        bloom_level=bloom_level,
        bloom_instruction=bloom_instruction,
    )

    q_id = f"Q_{uuid.uuid4().hex[:6].upper()}"

    # =====================================================================
    # SAVE QUESTION TO DB
    # =====================================================================

    db = state["db"]

    db.add(
        Conversation(
            conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
            session_id=state["session_id"],
            interview_id=state["interview_id"],
            speaker="agent",
            message=result["question"],
            question_id=q_id,
            timestamp=datetime.utcnow(),
        )
    )

    await db.commit()

    # =====================================================================
    # UPDATE STATE
    # =====================================================================

    return {
        **state,

        "current_question": result["question"],

        "current_question_id": q_id,

        "question_number": state["question_number"] + 1,
    }