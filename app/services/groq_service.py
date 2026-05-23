import json
from langchain_groq import ChatGroq
from langchain.messages import HumanMessage, SystemMessage
from app.config import settings
from app.exceptions import GroqAPIError


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.7,
    )


def _parse_json(raw: str) -> dict:
    """Strip markdown fences if present, then parse JSON."""
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


async def generate_interview_question(
    role: str,
    experience: int,
    skillset: list,
    previous_qa: list,
    difficulty: str = "medium",
) -> dict:
    """
    Returns: {"question": "...", "topic": "...", "difficulty": "..."}
    """
    history_text = "\n".join(
        [f"Q: {qa['question']}\nA: {qa['answer']}" for qa in previous_qa[-3:]]
    ) or "No previous questions yet."

    try:
        messages = [
            SystemMessage(content=(
                f"You are an expert technical interviewer.\n"
                f"Role: {role} | Experience: {experience} years | Skills: {', '.join(skillset)}\n"
                f"Generate ONE {difficulty}-difficulty interview question relevant to the role and skills.\n"
                f"Adjust complexity based on experience level.\n"
                f"Respond ONLY as valid JSON, no markdown, no extra text:\n"
                f'{{ "question": "...", "topic": "...", "difficulty": "{difficulty}" }}'
                f"\nUse the previous Q&A as context to avoid repetition:\n{history_text}"
                f"only ask theory based questions, no coding problems or puzzles."
                f"use blooms taxonomy to determine the difficulty level of the question."
                f"don't ask the same question if it has already been asked in the previous Q&A context."
            )),
            HumanMessage(content=f"Recent Q&A:\n{history_text}\n\nGenerate the next question."),
        ]
        response = _llm().invoke(messages)
        return _parse_json(response.content)
    except Exception as e:
        raise GroqAPIError(str(e))


async def evaluate_answer(question: str, answer: str, role: str) -> dict:
    """
    Returns: {"score": 75, "decision": "maintain_difficulty", "feedback": "..."}
    decision: increase_difficulty | maintain_difficulty | decrease_difficulty
    """
    try:
        messages = [
            SystemMessage(content=(
                f"You are evaluating a technical interview answer for a {role} position.\n"
                f"Score from 0 to 100.\n"
                f"Pick one decision: increase_difficulty, maintain_difficulty, decrease_difficulty.\n"
                f"Respond ONLY as valid JSON:\n"
                f'{{ "score": 75, "decision": "maintain_difficulty", "feedback": "..." }}'
            )),
            HumanMessage(content=f"Question: {question}\nAnswer: {answer}"),
        ]
        response = _llm().invoke(messages)
        return _parse_json(response.content)
    except Exception as e:
        raise GroqAPIError(str(e))


async def generate_final_report(candidate: dict, conversation: list) -> dict:
    """
    Returns full report with scores, strengths, improvements, recommendation.
    """
    qa_text = "\n".join(
        f"{'INTERVIEWER' if c['speaker'] == 'agent' else 'CANDIDATE'}: {c['message']}"
        for c in conversation
    )
    try:
        messages = [
            SystemMessage(content=(
                f"Generate a detailed interview evaluation report.\n"
                f"Candidate: {candidate['name']} | Role: {candidate['role']} | "
                f"Experience: {candidate['experience']} years\n"
                f"Respond ONLY as valid JSON with exactly these keys:\n"
                f"overall_score (0-100), technical_score (0-100), communication_score (0-100),\n"
                f"strengths (list of strings), improvements (list of strings),\n"
                f"recommendation (one of: Selected / On Hold / Rejected)"
            )),
            HumanMessage(content=f"Full interview transcript:\n{qa_text}"),
        ]
        response = _llm().invoke(messages)
        return _parse_json(response.content)
    except Exception as e:
        raise GroqAPIError(str(e))