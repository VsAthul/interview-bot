# app/agents/nodes/generate_report.py
import uuid
from datetime import datetime
from sqlalchemy import select
from app.agents.state import AgentState
from app.models import Conversation, Report, InterviewSession
from app.services.groq_service import generate_final_report


async def generate_report(state: AgentState) -> AgentState:
    """
    Node 5 — Fetches the full conversation from DB (source of truth),
    calls Groq to generate the report, saves report to DB.
    """
    db = state["db"]

    # Fetch from DB — more reliable than in-memory state
    result = await db.execute(
        select(Conversation)
        .where(Conversation.session_id == state["session_id"])
        .order_by(Conversation.timestamp)
    )
    all_messages = result.scalars().all()
    conv_list = [{"speaker": m.speaker, "message": m.message} for m in all_messages]

    # Generate report via Groq
    report_data = await generate_final_report(state["candidate"], conv_list)

    # Save report to DB
    report = Report(
        report_id=f"REP_{uuid.uuid4().hex[:6].upper()}",
        session_id=state["session_id"],
        interview_id=state["interview_id"],
        overall_score=report_data.get("overall_score"),
        technical_score=report_data.get("technical_score"),
        communication_score=report_data.get("communication_score"),
        strengths=report_data.get("strengths", []),
        improvements=report_data.get("improvements", []),
        recommendation=report_data.get("recommendation", "On Hold"),
    )
    db.add(report)

    # Mark session as completed
    sess_result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.session_id == state["session_id"])
    )
    session = sess_result.scalar_one_or_none()
    if session:
        session.status = "completed"
        session.completed_at = datetime.utcnow()

    await db.commit()

    return {**state, "report": report_data}