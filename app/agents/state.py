# app/agents/state.py
from typing import TypedDict, List, Optional, Any

class AgentState(TypedDict):
    candidate_id:        str
    session_id:          str
    interview_id:        str

    # Loaded from DB
    candidate:           dict        # {name, role, experience, skillset}

    # Conversation history (kept in memory for LLM context)
    conversation:        List[dict]  # [{"question": "...", "answer": "..."}]

    # Current turn
    current_question:    str
    current_question_id: str
    candidate_answer:    str

    # Progress tracking
    question_number: int
    max_questions: int
    difficulty:  str         # "easy" / "medium" / "hard"
    scores:      List[float]
    is_complete: bool

    # Final output
    report: Optional[dict]

    # DB session injected at graph invocation
    db: Any