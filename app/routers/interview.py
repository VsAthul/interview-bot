# app/routers/interview.py

import json as _json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Candidate, InterviewSession, Conversation, Report
from app.schemas import InterviewRequest
from app.exceptions import (
    CandidateNotFoundError,
    SessionNotFoundError,
    InterviewNotActiveError,
    ReportNotFoundError,                          # restored: was missing
)
from app.agents.graph import interview_graph
from config import max_questions

router = APIRouter(prefix="/api/interview", tags=["Interview"])


# ============================================================================
# HELPERS
# ============================================================================

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


def _state_to_json(state: dict) -> dict:
    return dict(state)                            # simplified: db no longer in state


# _restore_state deleted — db is now passed via config["configurable"]["db"]


# ============================================================================
# UNIFIED ENDPOINT
# ============================================================================

@router.post("")
async def interview(
    data: InterviewRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:                                        # added: return type annotation
    """
    Single unified interview endpoint.

    Routing by session status + payload:

        status=pending                  →  start  (phase=start)
        status=active + end=True        →  end    (phase=report)
        status=active + answer provided →  turn   (phase=answer)
        status=completed                →  error  (InterviewNotActiveError)
    """

    # LOAD SESSION

    sess_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.session_id == data.session_id
        )
    )
    session = sess_result.scalar_one_or_none()

    if not session:
        raise SessionNotFoundError(data.session_id)

    # -------------------------------------------------------------------------
    # ROUTE: START
    # -------------------------------------------------------------------------

    if session.status == "pending":

        cand_result = await db.execute(
            select(Candidate).where(
                Candidate.candidate_id == session.candidate_id
            )
        )
        candidate = cand_result.scalar_one_or_none()

        if not candidate:
            raise CandidateNotFoundError(session.candidate_id)

        session.status = "active"
        session.started_at = datetime.utcnow()
        await db.commit()

        state = {
            "phase":               "start",
            "candidate_id":        session.candidate_id,
            "session_id":          data.session_id,
            "interview_id":        session.interview_id,
            "candidate":           {},
            "conversation":        [],
            "current_question":    "",
            "current_question_id": "",
            "candidate_answer":    "",
            "question_number":     0,
            "max_questions":       max_questions,  # fixed: was hardcoded 7
            "difficulty":          "medium",
            "scores":              [],
            "bloom_level":         "understand",
            "is_complete":         False,
            "report":              None,
            "error":               None,
            # db removed — passed via config["configurable"]["db"]
        }

        state = await interview_graph.ainvoke(    # fixed: single ainvoke, removed duplicate
            state,
            config={
                "run_name":     f"start_{data.session_id}",
                "configurable": {"db": db},        # added: db passed via configurable
            },
        )

        session.agent_state = _state_to_json(state)

        greeting = (
            f"Welcome {state['candidate']['name']}! "
            f"Let's begin your {state['candidate']['role']} interview."
        )

        db.add(Conversation(                       # restored: was commented out
            conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
            session_id=data.session_id,
            interview_id=session.interview_id,     # fixed: was data.interview_id
            speaker="agent",
            message=greeting,
            timestamp=datetime.utcnow(),
        ))

        await db.commit()

        return {
            "success":          True,
            "phase":            "start",           # added: was missing
            "greeting_message": greeting,
            "question_id":      state["current_question_id"],
            "question":         state["current_question"],
            "question_number":  state["question_number"],
        }

    # -------------------------------------------------------------------------
    # ROUTE: END  (active + end=True)
    # -------------------------------------------------------------------------

    if session.status == "active" and data.end:

        if not session.agent_state:
            raise SessionNotFoundError(
                f"No agent state for session {data.session_id}"
            )

        state = session.agent_state                # fixed: _restore_state removed
        state["phase"]            = "report"
        state["is_complete"]      = True
        state["candidate_answer"] = ""

        state = await interview_graph.ainvoke(
            state,
            config={
                "run_name":     f"end_{data.session_id}",
                "configurable": {"db": db},        # added: db passed via configurable
            },
        )

        session.status       = "completed"
        session.completed_at = datetime.utcnow()
        session.agent_state  = _state_to_json(state)

        await db.commit()

        return {
            "success":          True,
            "phase":            "end",
            "message":          "Interview ended successfully",
            "report_generated": state.get("report") is not None,
        }

    # -------------------------------------------------------------------------
    # ROUTE: SUBMIT ANSWER  (active + answer provided)
    # -------------------------------------------------------------------------

    if session.status == "active":

        if not session.agent_state:
            raise SessionNotFoundError(
                f"No agent state for session {data.session_id}"
            )

        if not data.answer:
            raise InterviewNotActiveError()

        state = session.agent_state                # fixed: _restore_state removed
        state["phase"]               = "answer"
        state["candidate_answer"]    = data.answer
        state["current_question_id"] = data.question_id

        state = await interview_graph.ainvoke(
            state,
            config={
                "run_name":     f"turn_{data.session_id}_{state['question_number']}",
                "configurable": {"db": db},        # added: db passed via configurable
            },
        )

        session.agent_state = _state_to_json(state)
        await db.commit()

        scores_list   = state.get("scores", [])
        conv_list     = state.get("conversation", [])
        last_score    = scores_list[-1] if scores_list else None
        last_question = conv_list[-1]["question"] if conv_list else data.answer

        if state["is_complete"]:
            session.status       = "completed"
            session.completed_at = datetime.utcnow()
            await db.commit()

            return {
                "success":       True,
                "phase":         "complete",
                "is_complete":   True,
                "report":        state.get("report") or {},
                "last_score":    last_score,
                "last_question": last_question,
            }

        return {
            "success":          True,
            "phase":            "answer",
            "is_complete":      False,
            "question_id":      state["current_question_id"],
            "question":         state["current_question"],
            "question_number":  state["question_number"],
            "difficulty_level": state["difficulty"],
            "last_score":       last_score,
            "last_question":    last_question,
        }

    # ALREADY COMPLETED

    raise InterviewNotActiveError()


# ============================================================================
# READ-ONLY ENDPOINTS
# ============================================================================

@router.get("/report/{session_id}")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:                                        # added: return type annotation
    result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = result.scalars().first()

    if not report:
        raise ReportNotFoundError(session_id)     # fixed: was SessionNotFoundError

    return {
        "success":             True,
        "overall_score":       report.overall_score,
        "technical_score":     report.technical_score,
        "communication_score": report.communication_score,
        "strengths":           _ensure_list(report.strengths),
        "improvements":        _ensure_list(report.improvements),
        "recommendation":      report.recommendation,
    }


@router.get("/conversation/{session_id}")
async def get_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:                                        # added: return type annotation
    result = await db.execute(
        select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.timestamp)
    )
    messages = result.scalars().all()

    return {
        "success": True,
        "conversation": [
            {
                "speaker":   m.speaker,
                "message":   m.message,
                "timestamp": str(m.timestamp),
            }
            for m in messages
        ],
    }