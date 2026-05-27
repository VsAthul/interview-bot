# app/agents/nodes/load_candidate.py
import json as _json
from sqlalchemy import select
from app.models import Candidate
from app.agents.state import AgentState
from app.exceptions import CandidateNotFoundError


def _ensure_list(value : str | list | None) -> list:
    """Coerce SQLite JSON column back to a Python list."""
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


async def load_candidate(state: AgentState) -> AgentState:
    """
    Node 1 — Fetches candidate profile from DB.
    Must run first: every other node uses state["candidate"].
    """
    db = state["db"]
    result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == state["candidate_id"])
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise CandidateNotFoundError(state["candidate_id"])

    return {
        **state,
        "candidate": {
            "name":       candidate.name,
            "role":       candidate.role,
            "experience": candidate.experience,
            "skillset":   _ensure_list(candidate.skillset),  # safe SQLite read
        }
    }