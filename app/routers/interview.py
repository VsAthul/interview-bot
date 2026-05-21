# app/routers/interview.py
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
from app.services.groq_service import generate_interview_question, generate_final_report


router = APIRouter(prefix="/api/interview", tags=["Interview"])


@router.post("/session")
async def create_session(
    data: SessionCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == data.candidate_id)
    )
    if not result.scalar_one_or_none():
        raise CandidateNotFoundError(data.candidate_id)

    # Block if a session is already active
    active = await db.execute(
        select(InterviewSession).where(
            InterviewSession.candidate_id == data.candidate_id,
            InterviewSession.status == "active"
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


@router.post("/start")
async def start_interview(
    data: InterviewStartRequest,
    db: AsyncSession = Depends(get_db)
):
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)

    cand_result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == session.candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()

    # Mark active
    session.status     = "active"
    session.started_at = datetime.utcnow()
    await db.commit()

    # Generate greeting + first question
    greeting = f"Welcome {candidate.name}! Let's begin your {candidate.role} interview."
    q_result = await generate_interview_question(
        role=candidate.role, experience=candidate.experience,
        skillset=candidate.skillset, previous_qa=[], difficulty="medium"
    )
    q_id = f"Q_{uuid.uuid4().hex[:6].upper()}"

    # ── Save greeting to DB immediately ───────────────────────────────────────
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=data.session_id,
        interview_id=data.interview_id,
        speaker="agent",
        message=greeting,
        timestamp=datetime.utcnow(),
    ))
    # ── Save first question to DB immediately ─────────────────────────────────
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=data.session_id,
        interview_id=data.interview_id,
        speaker="agent",
        message=q_result["question"],
        question_id=q_id,
        timestamp=datetime.utcnow(),
    ))
    await db.commit()

    return {
        "success":          True,
        "greeting_message": greeting,
        "question_id":      q_id,
        "question":         q_result["question"],
        "question_number":  1,
    }


@router.post("/answer")
async def save_answer(
    data: AnswerSaveRequest,
    db: AsyncSession = Depends(get_db)
):
    """Saves a transcribed candidate answer to DB."""
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

    return {
        "success":   True,
        "answer_id": f"ANS_{uuid.uuid4().hex[:6].upper()}",
        "message":   "Answer stored successfully",
    }


@router.post("/next-question")
async def next_question(
    data: NextQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)
    if session.status != "active":
        raise InterviewNotActiveError()

    cand_result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == session.candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()

    q_result = await generate_interview_question(
        role=candidate.role, experience=candidate.experience,
        skillset=candidate.skillset,
        previous_qa=[{"question": data.previous_question, "answer": data.candidate_answer}],
        difficulty="medium",
    )
    q_id = f"Q_{uuid.uuid4().hex[:6].upper()}"

    # ── Save new question to DB immediately ───────────────────────────────────
    db.add(Conversation(
        conversation_id=f"CONV_{uuid.uuid4().hex[:8].upper()}",
        session_id=data.session_id,
        interview_id=session.interview_id,
        speaker="agent",
        message=q_result["question"],
        question_id=q_id,
        timestamp=datetime.utcnow(),
    ))
    await db.commit()

    return {
        "success":            True,
        "question_id":        q_id,
        "question":           q_result["question"],
        "difficulty_level":   q_result.get("difficulty", "medium"),
    }


@router.post("/end")
async def end_interview(
    data: EndInterviewRequest,
    db: AsyncSession = Depends(get_db)
):
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)

    session.status       = "completed"
    session.completed_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Interview completed successfully"}


@router.post("/report/generate")
async def generate_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    sess_result = await db.execute(
        select(InterviewSession).where(InterviewSession.session_id == data.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(data.session_id)

    cand_result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == session.candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()

    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.session_id == data.session_id)
        .order_by(Conversation.timestamp)
    )
    conv_list = [
        {"speaker": c.speaker, "message": c.message}
        for c in conv_result.scalars().all()
    ]

    report_data = await generate_final_report(
        {"name": candidate.name, "role": candidate.role, "experience": candidate.experience},
        conv_list,
    )

    report = Report(
        report_id=f"REP_{uuid.uuid4().hex[:6].upper()}",
        session_id=data.session_id,
        interview_id=session.interview_id,
        overall_score=report_data.get("overall_score"),
        technical_score=report_data.get("technical_score"),
        communication_score=report_data.get("communication_score"),
        strengths=report_data.get("strengths", []),
        improvements=report_data.get("improvements", []),
        recommendation=report_data.get("recommendation", "On Hold"),
    )
    db.add(report)
    await db.commit()

    return {"success": True, "report_id": report.report_id, **report_data}


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
        "strengths":           report.strengths,
        "improvements":        report.improvements,
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
        "success":      True,
        "conversation": [
            {"speaker": m.speaker, "message": m.message, "timestamp": str(m.timestamp)}
            for m in messages
        ],
    }