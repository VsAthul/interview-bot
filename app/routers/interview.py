# app/routers/interview.py
"""
Interview router — LangGraph edition.

Flow
────
POST /session          Create session row (no graph yet)
POST /start            Run graph: load_candidate → generate_question
                       Persist AgentState to session.agent_state (JSON)
POST /submit-answer    Resume graph from saved state:
                         evaluate_answer → check_completion →
                           generate_question   (if more questions)
                         OR
                           generate_report     (if complete)
                       Persist updated AgentState back to DB
POST /end              Early exit — runs generate_report node directly
GET  /report/:id       Read existing Report row (no Groq call)
GET  /conversation/:id Read Conversation rows

Legacy endpoints kept for compatibility
────────────────────────────────────────
POST /answer           Thin wrapper — just saves answer text to DB
POST /next-question    Returns next question from saved agent_state
POST /report/generate  Alias for the graph-driven report generation
"""

import json as _json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Candidate, InterviewSession, Conversation, Report
from app.schemas import (
    SessionCreateRequest, InterviewStartRequest,
    AnswerSaveRequest, NextQuestionRequest,
    EndInterviewRequest, ReportGenerateRequest,
)
from app.exceptions import (
    CandidateNotFoundError, SessionNotFoundError,
    InterviewAlreadyActiveError, InterviewNotActiveError,
)
from app.agents.graph import start_graph, answer_graph, report_graph


router = APIRouter(prefix="/api/interview", tags=["Interview"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_list(value) -> list:
    """Coerce SQLite JSON column value to a Python list."""
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
    """Strip non-serialisable keys (db session) before persisting to DB."""
    return {k: v for k, v in state.items() if k != "db"}


def _restore_state(saved: dict, db: AsyncSession) -> dict:
    """Re-attach the live DB session to a restored AgentState."""
    return {**saved, "db": db}


# ── Session ───────────────────────────────────────────────────────────────────

@router.post("/session")
async def create_session(
    data: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == data.candidate_id)
    )
    if not result.scalar_one_or_none():
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
        "success":      True,
        "session_id":   session.session_id,
        "interview_id": session.interview_id,
    }


# ── Start ─────────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_interview(
    data: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initialises AgentState and runs the graph through:
      load_candidate → generate_question
    The graph pauses after generate_question (it needs the candidate's
    answer before it can evaluate). State is persisted to DB.
    """
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)

    # Mark active
    session.status     = "active"
    session.started_at = datetime.utcnow()
    await db.commit()

    # ── Build initial AgentState ──────────────────────────────────────────────
    initial_state = {
        "candidate_id":        session.candidate_id,
        "session_id":          data.session_id,
        "interview_id":        data.interview_id,
        "candidate":           {},          # filled by load_candidate node
        "conversation":        [],
        "current_question":    "",
        "current_question_id": "",
        "candidate_answer":    "",
        "question_number":     0,
        "max_questions":       7,
        "difficulty":          "medium",
        "scores":              [],
        "is_complete":         False,
        "report":              None,
        "db":                  db,
    }

    # ── Run graph: load_candidate → generate_question ─────────────────────────
    # We invoke only these two nodes by stopping before evaluate_answer.
    # LangGraph runs the full graph up to END, but generate_question
    # does NOT call evaluate_answer — the graph pauses waiting for the
    # next invocation. We control resumption by storing state + re-invoking.
    state = await start_graph.ainvoke(
        initial_state,
        config={"run_name": f"start_{data.session_id}"},
    )

    # ── Persist state to DB (without db session object) ───────────────────────
    session.agent_state = _state_to_json(state)
    await db.commit()

    # ── Save greeting to DB ───────────────────────────────────────────────────
    greeting = f"Welcome {state['candidate']['name']}! Let's begin your {state['candidate']['role']} interview."
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=data.session_id,
        interview_id=data.interview_id,
        speaker="agent",
        message=greeting,
        timestamp=datetime.utcnow(),
    ))
    await db.commit()

    return {
        "success":          True,
        "greeting_message": greeting,
        "question_id":      state["current_question_id"],
        "question":         state["current_question"],
        "question_number":  state["question_number"],
    }


# ── Submit Answer (graph-driven) ──────────────────────────────────────────────

@router.post("/submit-answer")
async def submit_answer(
    data: AnswerSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Single endpoint that drives one full graph turn:
      evaluate_answer → check_completion → generate_question OR generate_report

    Replaces the old separate calls to:
      /answer + /reflection/evaluate + /next-question (or /end + /report/generate)
    """
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)
    if session.status != "active":
        raise InterviewNotActiveError()

    # ── Restore AgentState from DB ────────────────────────────────────────────
    saved = session.agent_state
    if not saved:
        raise SessionNotFoundError(f"No agent state for session {data.session_id}")

    state = _restore_state(saved, db)

    # ── Inject this turn's answer into state ──────────────────────────────────
    state["candidate_answer"]    = data.answer_text
    state["current_question_id"] = data.question_id

    # ── Run graph: evaluate_answer → check_completion → next node ────────────
    # The graph will:
    #   1. evaluate_answer  — scores answer, saves to DB, adjusts difficulty
    #   2. check_completion — sets is_complete flag
    #   3a. generate_question — if not complete (saves question to DB)
    #   3b. generate_report   — if complete (saves report to DB, marks session done)
    state = await answer_graph.ainvoke(
        state,
        config={"run_name": f"turn_{data.session_id}_{state['question_number']}"},
    )

    # ── Persist updated state ─────────────────────────────────────────────────
    session.agent_state = _state_to_json(state)
    await db.commit()

    # ── Build response ────────────────────────────────────────────────────────
    # Extract the score for the answer just evaluated
    # state["scores"] is a list; the last entry is this turn's score.
    # state["conversation"] last entry has the question that was just answered.
    scores_list = state.get("scores", [])
    conv_list   = state.get("conversation", [])
    last_score    = scores_list[-1] if scores_list else None
    last_question = conv_list[-1]["question"] if conv_list else data.answer_text

    if state["is_complete"]:
        # Report was generated by the graph
        report = state.get("report") or {}
        return {
            "success":      True,
            "is_complete":  True,
            "report":       report,
            "last_score":   last_score,
            "last_question": last_question,
        }

    return {
        "success":         True,
        "is_complete":     False,
        "question_id":     state["current_question_id"],
        "question":        state["current_question"],
        "question_number": state["question_number"],
        "difficulty_level": state["difficulty"],
        "last_score":      last_score,
        "last_question":   last_question,
    }


# ── End Interview (early exit) ────────────────────────────────────────────────

@router.post("/end")
async def end_interview(
    data: EndInterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ends interview early. Restores state, forces is_complete=True,
    then runs generate_report node directly via the graph.
    """
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)

    if session.agent_state:
        state = _restore_state(session.agent_state, db)
        state["is_complete"]    = True
        state["candidate_answer"] = ""   # no answer this turn
        # Run report_graph directly — generate_report node saves to DB
        state = await report_graph.ainvoke(
            state,
            config={"run_name": f"end_{data.session_id}"},
        )
        session.agent_state = None
    else:
        # Fallback: just mark completed
        session.status       = "completed"
        session.completed_at = datetime.utcnow()

    await db.commit()
    return {"success": True, "message": "Interview ended successfully"}


# ── Report (read from DB — no Groq call) ─────────────────────────────────────

@router.post("/report/generate")
async def generate_report_compat(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Compatibility endpoint — reads the report already saved by the graph.
    If not found (e.g. interview ended before graph ran), generates it now.
    """
    result = await db.execute(
        select(Report).where(Report.session_id == data.session_id)
    )
    report = result.scalar_one_or_none()

    if report:
        return {
            "success":             True,
            "report_id":           report.report_id,
            "overall_score":       report.overall_score,
            "technical_score":     report.technical_score,
            "communication_score": report.communication_score,
            "strengths":           _ensure_list(report.strengths),
            "improvements":        _ensure_list(report.improvements),
            "recommendation":      report.recommendation,
        }

    # Report not yet in DB — shouldn't normally happen, but handle gracefully
    raise SessionNotFoundError(f"Report not found for session {data.session_id}")


@router.get("/report/{session_id}")
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise SessionNotFoundError(session_id)

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
async def get_conversation(session_id: str, db: AsyncSession = Depends(get_db)):
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


# ── Legacy endpoints (kept for backward compat) ───────────────────────────────

@router.post("/answer")
async def save_answer_legacy(
    data: AnswerSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Legacy — use /submit-answer instead. Saves answer to DB only."""
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)
    if session.status != "active":
        raise InterviewNotActiveError()

    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=data.session_id,
        interview_id=session.interview_id,
        speaker="candidate",
        message=data.answer_text,
        question_id=data.question_id,
        timestamp=datetime.utcnow(),
    ))
    await db.commit()
    return {"success": True, "message": "Answer stored"}


@router.post("/next-question")
async def next_question_legacy(
    data: NextQuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy — use /submit-answer instead.
    Reads current question from saved agent_state to stay in sync.
    """
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)
    if session.status != "active":
        raise InterviewNotActiveError()

    saved = session.agent_state
    if not saved:
        raise SessionNotFoundError(f"No agent state for {data.session_id}")

    return {
        "success":          True,
        "question_id":      saved.get("current_question_id", ""),
        "question":         saved.get("current_question", ""),
        "difficulty_level": saved.get("difficulty", "medium"),
    }