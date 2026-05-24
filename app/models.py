# app/models.py
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base

def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id = Column(String, primary_key=True, default=lambda: gen_id("CAND"))
    name         = Column(String, nullable=False)
    email        = Column(String, unique=True, nullable=False)
    phone        = Column(String, nullable=True)
    role         = Column(String, nullable=False)
    experience   = Column(Integer, nullable=False)
    skillset     = Column(JSON)
    created_at   = Column(DateTime, server_default=func.now())


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    session_id   = Column(String, primary_key=True, default=lambda: gen_id("SESSION"))
    interview_id = Column(String, unique=True, nullable=False, default=lambda: gen_id("INT"))
    candidate_id = Column(String, nullable=False)
    status       = Column(String, default="pending")   # pending / active / completed

    # ── LangGraph agent state persisted between HTTP requests ─────────────────
    # Stores the full AgentState dict as JSON so the graph can resume
    # on each answer submission without losing conversation history,
    # scores, difficulty, or question count.
    agent_state  = Column(JSON, nullable=True)

    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Conversation(Base):
    """
    Every single message — agent question OR candidate answer —
    is saved HERE at the moment it is generated. Never batched.
    """
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True, default=lambda: gen_id("CONV"))
    session_id      = Column(String, nullable=False)
    interview_id    = Column(String, nullable=False)
    speaker         = Column(String, nullable=False)   # "agent" or "candidate"
    message         = Column(Text, nullable=False)
    question_id     = Column(String, nullable=True)
    timestamp       = Column(DateTime, server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    report_id           = Column(String, primary_key=True, default=lambda: gen_id("REP"))
    session_id          = Column(String, nullable=False)
    interview_id        = Column(String, nullable=False)
    overall_score       = Column(Float, nullable=True)
    technical_score     = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    strengths           = Column(JSON)
    improvements        = Column(JSON)
    recommendation      = Column(String, nullable=True)
    created_at          = Column(DateTime, server_default=func.now())