# app/agents/nodes/generate_question.py
import uuid
from datetime import datetime
from app.agents.state import AgentState
from app.models import Conversation
from app.services.groq_service import generate_interview_question


async def generate_question(state: AgentState) -> AgentState:
    """
    Node 2 — Generates the next interview question using Groq.
    Saves the question to DB IMMEDIATELY after generation.
    """
    c = state["candidate"]
    result = await generate_interview_question(
        role=c["role"],
        experience=c["experience"],
        skillset=c["skillset"],
        previous_qa=state["conversation"],
        difficulty=state["difficulty"],
    )

    q_id = f"Q_{uuid.uuid4().hex[:6].upper()}"

    # ── Save to DB right away — never wait until the end ──────────────────────
    db = state["db"]
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=state["session_id"],
        interview_id=state["interview_id"],
        speaker="agent",
        message=result["question"],
        question_id=q_id,
        timestamp=datetime.utcnow(),
    ))
    await db.commit()

    return {
        **state,
        "current_question":    result["question"],
        "current_question_id": q_id,
        "question_number":     state["question_number"] + 1,
    }