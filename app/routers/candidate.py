import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Candidate, InterviewSession
from app.schemas import CandidateRegisterRequest
from app.exceptions import DuplicateEmailError

router = APIRouter(prefix="/api/candidate", tags=["Candidate"])


@router.post("/register")
async def register_candidate(
    data: CandidateRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Candidate).where(Candidate.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise DuplicateEmailError(data.email)

    candidate = Candidate(
        candidate_id=f"CAND_{uuid.uuid4().hex[:6].upper()}",
        name=data.name,
        email=data.email,
        phone=data.phone,
        role=data.role,
        experience=data.experience,
        skillset=data.skillset,
    )
    db.add(candidate)
    await db.flush()  # get candidate_id before commit

    session = InterviewSession(
        session_id=f"SESS_{uuid.uuid4().hex[:8].upper()}",
        candidate_id=candidate.candidate_id,
    )
    db.add(session)
    await db.commit()

    return {
        "success": True,
        "session_id": session.session_id,
        "candidate_id": candidate.candidate_id,
        "message": "Candidate registered successfully",
    }