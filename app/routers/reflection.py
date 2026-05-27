from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import InterviewSession, Candidate
from app.schemas import ReflectionRequest
from app.exceptions import CandidateNotFoundError, SessionNotFoundError
from app.services.groq_service import evaluate_answer

router = APIRouter(prefix="/api/reflection", tags=["Reflection"])


@router.post("/evaluate")
async def reflect(data: ReflectionRequest, db: AsyncSession = Depends(get_db)):
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
    if not candidate:
        raise CandidateNotFoundError(session.candidate_id)

    result = await evaluate_answer(
        question=data.question,
        answer=data.candidate_answer,
        role=candidate.role,
    )
    return {
        "success": True,
        "answer_score": result.get("score"),
        "decision": result.get("decision"),
        "feedback": result.get("feedback"),
    }