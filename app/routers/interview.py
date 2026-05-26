import json as _json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Candidate, InterviewSession, Conversation, Report
from app.schemas import (
    SessionCreateRequest,
    InterviewStartRequest,
    AnswerSaveRequest,
    NextQuestionRequest,
    EndInterviewRequest,
    ReportGenerateRequest,
)
from app.exceptions import (
    CandidateNotFoundError,
    SessionNotFoundError,
    InterviewAlreadyActiveError,
    InterviewNotActiveError,
)

# ONLY ONE GRAPH NOW
from app.agents.graph import interview_graph
from config import max_questions


router = APIRouter(prefix="/api/interview", tags=["Interview"])


# ============================================================================
# HELPERS
# ============================================================================


def _ensure_list(value) -> list:
    """Coerce SQLite JSON column value to Python list."""

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
    """
    Removes non-serializable objects before saving state.
    """

    return {
        k: v
        for k, v in state.items()
        if k != "db"
    }



def _restore_state(saved: dict, db: AsyncSession) -> dict:
    """
    Re-attaches DB session to persisted state.
    """

    return {
        **saved,
        "db": db,
    }


# ============================================================================
# CREATE SESSION
# ============================================================================


@router.post("/session")
async def create_session(
    data: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Candidate).where(
            Candidate.candidate_id == data.candidate_id
        )
    )

    candidate = result.scalar_one_or_none()

    if not candidate:
        raise CandidateNotFoundError(data.candidate_id)

    active = await db.execute(
        select(InterviewSession).where(
            InterviewSession.candidate_id == data.candidate_id,
            InterviewSession.status == "active",
        )
    )

    if active.scalar_one_or_none():
        raise InterviewAlreadyActiveError()

    session = InterviewSession(
        session_id=f"SESSION_{uuid.uuid4().hex[:6].upper()}",
        interview_id=f"INT_{uuid.uuid4().hex[:6].upper()}",
        candidate_id=data.candidate_id,
        status="pending",
    )

    db.add(session)
    await db.commit()

    return {
        "success": True,
        "session_id": session.session_id,
        "interview_id": session.interview_id,
    }


# ============================================================================
# START INTERVIEW
# ============================================================================


@router.post("/start")
async def start_interview(
    data: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Starts interview.

    Unified graph flow:

        phase=start
            ↓
        load_candidate
            ↓
        generate_question
    """

    sess_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.session_id == data.session_id
        )
    )

    session = sess_result.scalar_one_or_none()

    if not session:
        raise SessionNotFoundError(data.session_id)

    session.status = "active"
    session.started_at = datetime.utcnow()

    await db.commit()


    initial_state = {
        "phase": "start",

        "candidate_id": session.candidate_id,
        "session_id": data.session_id,
        "interview_id": data.interview_id,

        "candidate": {},
        "conversation": [],

        "current_question": "",
        "current_question_id": "",
        "candidate_answer": "",

        "question_number": 0,
        "max_questions": max_questions,

        "difficulty": "medium",
        "scores": [],
        "bloom_level": "understand",
        "is_complete": False,
        "report": None,
        "error": None,

        "db": db,
    }


    state = await interview_graph.ainvoke(
        initial_state,
        config={
            "run_name": f"start_{data.session_id}",
        },
    )


    session.agent_state = _state_to_json(state)

    await db.commit()


    greeting = (
        f"Welcome {state['candidate']['name']}! "
        f"Let's begin your {state['candidate']['role']} interview."
    )

    db.add(
        Conversation(
            conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
            session_id=data.session_id,
            interview_id=data.interview_id,
            speaker="agent",
            message=greeting,
            timestamp=datetime.utcnow(),
        )
    )

    await db.commit()

    return {
        "success": True,
        "greeting_message": greeting,
        "question_id": state["current_question_id"],
        "question": state["current_question"],
        "question_number": state["question_number"],
    }




@router.post("/submit-answer")
async def submit_answer(
    data: AnswerSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Runs one interview turn.

    Unified graph flow:

        phase=answer
            ↓
        evaluate_answer
            ↓
        check_completion
            ↓
        generate_question OR generate_report
    """

    sess_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.session_id == data.session_id
        )
    )

    session = sess_result.scalar_one_or_none()

    if not session:
        raise SessionNotFoundError(data.session_id)

    if session.status != "active":
        raise InterviewNotActiveError()

    saved = session.agent_state

    if not saved:
        raise SessionNotFoundError(
            f"No agent state for session {data.session_id}"
        )


    state = _restore_state(saved, db)

    # IMPORTANT
    # This drives graph routing.
    state["phase"] = "answer"

    state["candidate_answer"] = data.answer_text
    state["current_question_id"] = data.question_id


    state = await interview_graph.ainvoke(
        state,
        config={
            "run_name": (
                f"turn_{data.session_id}_"
                f"{state['question_number']}"
            ),
        },
    )


    session.agent_state = _state_to_json(state)

    await db.commit()


    scores_list = state.get("scores", [])
    conv_list = state.get("conversation", [])

    last_score = scores_list[-1] if scores_list else None

    last_question = (
        conv_list[-1]["question"]
        if conv_list
        else data.answer_text
    )


    if state["is_complete"]:

        session.status = "completed"
        session.completed_at = datetime.utcnow()

        await db.commit()

        return {
            "success": True,
            "is_complete": True,
            "report": state.get("report") or {},
            "last_score": last_score,
            "last_question": last_question,
        }


    return {
        "success": True,
        "is_complete": False,
        "question_id": state["current_question_id"],
        "question": state["current_question"],
        "question_number": state["question_number"],
        "difficulty_level": state["difficulty"],
        "last_score": last_score,
        "last_question": last_question,
    }



@router.post("/end")
async def end_interview(
    data: EndInterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ends interview early.

    Unified graph flow:

        phase=report
            ↓
        generate_report
    """

    sess_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.session_id == data.session_id
        )
    )

    session = sess_result.scalar_one_or_none()

    if not session:
        raise SessionNotFoundError(data.session_id)

    if session.status != "active":
        raise InterviewNotActiveError()

    saved = session.agent_state

    if not saved:
        raise SessionNotFoundError(
            f"No agent state for session {data.session_id}"
        )


    state = _restore_state(saved, db)

    # IMPORTANT
    # Route unified graph correctly.
    state["phase"] = "report"

    # Force interview completion
    state["is_complete"] = True

    # No pending answer
    state["candidate_answer"] = ""


    state = await interview_graph.ainvoke(
        state,
        config={
            "run_name": f"end_{data.session_id}",
        },
    )

    print("FINAL REPORT STATE:", state.get("report"))


    session.status = "completed"
    session.completed_at = datetime.utcnow()

    # Keep state for debugging/history
    session.agent_state = _state_to_json(state)

    await db.commit()


    return {
        "success": True,
        "message": "Interview ended successfully",
        "report_generated": state.get("report") is not None,
    }



@router.get("/report/{session_id}")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Report).where(
            Report.session_id == session_id
        )
    )

    report = result.scalars().first()

    if not report:
        raise SessionNotFoundError(
            f"Report not found for session {session_id}"
        )

    return {
        "success": True,

        "overall_score": report.overall_score,

        "technical_score": report.technical_score,

        "communication_score": report.communication_score,

        "strengths": _ensure_list(report.strengths),

        "improvements": _ensure_list(report.improvements),

        "recommendation": report.recommendation,
    }



@router.get("/conversation/{session_id}")
async def get_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.session_id == session_id
        )
        .order_by(Conversation.timestamp)
    )

    messages = result.scalars().all()

    return {
        "success": True,

        "conversation": [
            {
                "speaker": m.speaker,
                "message": m.message,
                "timestamp": str(m.timestamp),
            }
            for m in messages
        ],
    }