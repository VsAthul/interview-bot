# app/agents/nodes/generate_report.py

import json as _json
import uuid

from sqlalchemy import select

from app.agents.state import AgentState
from app.models import (
    Conversation,
    Report,
)

from app.services.groq_service import generate_final_report


def _ensure_list(value) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []

    return []


async def generate_report(state: AgentState) -> AgentState:
    """
    Final graph node.

    Responsibilities:
    - Fetch conversation
    - Generate report via LLM
    - Persist report to DB
    - Return updated state

    IMPORTANT:
    This node should NOT:
    - clear session state
    - finalize orchestration lifecycle
    - mutate session lifecycle aggressively
    """

    db = state["db"]

    # =====================================================================
    # FETCH CONVERSATION
    # =====================================================================

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.session_id == state["session_id"]
        )
        .order_by(Conversation.timestamp)
    )

    all_messages = result.scalars().all()

    conv_list = [
        {
            "speaker": m.speaker,
            "message": m.message,
        }
        for m in all_messages
    ]

    # =====================================================================
    # GENERATE REPORT
    # =====================================================================

    report_data = await generate_final_report(
        state["candidate"],
        conv_list,
    )

    # =====================================================================
    # PREVENT DUPLICATE REPORTS
    # =====================================================================

    existing = await db.execute(
        select(Report).where(
            Report.session_id == state["session_id"]
        )
    )

    existing_report = existing.scalars().first()

    if not existing_report:

        report = Report(
            report_id=f"REP_{uuid.uuid4().hex[:6].upper()}",
            session_id=state["session_id"],
            interview_id=state["interview_id"],

            overall_score=report_data.get("overall_score"),
            technical_score=report_data.get("technical_score"),
            communication_score=report_data.get("communication_score"),

            strengths=_ensure_list(
                report_data.get("strengths")
            ),

            improvements=_ensure_list(
                report_data.get("improvements")
            ),

            recommendation=report_data.get(
                "recommendation",
                "On Hold",
            ),
        )

        db.add(report)

    # =====================================================================
    # SAVE
    # =====================================================================

    await db.commit()

    # =====================================================================
    # UPDATE STATE
    # =====================================================================

    state["report"] = report_data
    state["is_complete"] = True

    return state