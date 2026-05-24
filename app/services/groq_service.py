# app/services/groq_service.py

import json

from langchain_groq import ChatGroq
from langchain.messages import HumanMessage, SystemMessage

from app.config import settings
from app.exceptions import GroqAPIError


# ============================================================================
# LLM FACTORY
# ============================================================================

def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.7,
    )


# ============================================================================
# SAFE JSON PARSER
# ============================================================================

def _parse_json(raw: str) -> dict:
    """
    Robust JSON extraction from LLM responses.

    Handles:
    - markdown fences
    - extra explanations
    - malformed wrappers
    - accidental text before/after JSON
    """

    try:

        cleaned = raw.strip()

        # Remove markdown fences
        cleaned = cleaned.replace("```json", "")
        cleaned = cleaned.replace("```", "")
        cleaned = cleaned.strip()

        # Extract JSON object safely
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

        return json.loads(cleaned)

    except Exception as e:

        raise GroqAPIError(
            f"Failed to parse LLM JSON response.\n\n"
            f"Raw Response:\n{raw}\n\n"
            f"Error: {str(e)}"
        )


# ============================================================================
# QUESTION GENERATION
# ============================================================================

async def generate_interview_question(
    role: str,
    experience: int,
    skillset: list,
    previous_qa: list,
    difficulty: str = "medium",

    # NEW
    bloom_level: str = "understand",
    bloom_instruction: str = "",
) -> dict:
    """
    Returns:
    {
        "question": "...",
        "topic": "...",
        "difficulty": "..."
    }
    """

    history_text = "\n".join(
        [
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in previous_qa[-3:]
        ]
    ) or "No previous questions yet."

    try:

        messages = [
            SystemMessage(
                content=(
                    f"You are an expert technical interviewer.\n\n"

                    f"Role: {role}\n"
                    f"Experience: {experience} years\n"
                    f"Skills: {', '.join(skillset)}\n\n"

                    f"Generate ONE {difficulty}-difficulty "
                    f"technical interview question.\n\n"

                    f"Rules:\n"
                    f"- Only theory-based questions\n"
                    f"- No coding problems\n"
                    f"- No puzzles\n"
                    f"- Avoid repetition\n"
                    f"Generate ONE {difficulty}-difficulty "
                    f"technical interview question.\n\n"

                    f"Bloom's Taxonomy Level: {bloom_level}\n"
                    f"{bloom_instruction}\n\n"
                    f"- Use Bloom's Taxonomy to adapt difficulty\n"
                    f"- Adjust complexity based on experience\n\n"

                    f"Use previous Q&A as context:\n"
                    f"{history_text}\n\n"

                    f"Respond ONLY with STRICT VALID JSON.\n"
                    f"Do NOT include markdown.\n"
                    f"Do NOT include explanations.\n\n"

                    f'Required JSON format:\n'
                    f'{{\n'
                    f'  "question": "string",\n'
                    f'  "topic": "string",\n'
                    f'  "difficulty": "{difficulty}"\n'
                    f'}}'
                )
            ),

            HumanMessage(
                content=(
                    f"Generate the next interview question."
                )
            ),
        ]

        response = _llm().invoke(messages)

        parsed = _parse_json(response.content)

        return {
            "question": parsed.get(
                "question",
                "Tell me about yourself."
            ),

            "topic": parsed.get(
                "topic",
                "General"
            ),

            "difficulty": parsed.get(
                "difficulty",
                difficulty
            ),
        }

    except Exception as e:
        raise GroqAPIError(str(e))


# ============================================================================
# ANSWER EVALUATION
# ============================================================================

async def evaluate_answer(
    question: str,
    answer: str,
    role: str,
) -> dict:
    """
    Returns:
    {
        "score": 75,
        "decision": "maintain_difficulty",
        "feedback": "..."
    }
    """

    try:

        messages = [

            SystemMessage(
                content=(
                    f"You are evaluating a technical interview answer.\n\n"

                    f"Role: {role}\n\n"

                    f"Evaluate:\n"
                    f"- technical correctness\n"
                    f"- clarity\n"
                    f"- completeness\n"
                    f"- communication\n\n"

                    f"Score from 0 to 100.\n\n"

                    f"Decision MUST be one of:\n"
                    f"- increase_difficulty\n"
                    f"- maintain_difficulty\n"
                    f"- decrease_difficulty\n\n"

                    f"Respond ONLY with STRICT VALID JSON.\n"
                    f"Do NOT include markdown.\n"
                    f"Do NOT include explanations.\n\n"

                    f'Required JSON format:\n'
                    f'{{\n'
                    f'  "score": 75,\n'
                    f'  "decision": "maintain_difficulty",\n'
                    f'  "feedback": "string"\n'
                    f'}}'
                )
            ),

            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Answer:\n{answer}"
                )
            ),
        ]

        response = _llm().invoke(messages)

        parsed = _parse_json(response.content)

        return {
            "score": parsed.get("score", 50),

            "decision": parsed.get(
                "decision",
                "maintain_difficulty"
            ),

            "feedback": parsed.get(
                "feedback",
                "Average response."
            ),
        }

    except Exception as e:
        raise GroqAPIError(str(e))


# ============================================================================
# FINAL REPORT GENERATION
# ============================================================================

async def generate_final_report(
    candidate: dict,
    conversation: list,
) -> dict:
    """
    Generates final interview report.

    Returns:
    {
        "overall_score": int,
        "technical_score": int,
        "communication_score": int,
        "strengths": [],
        "improvements": [],
        "recommendation": str
    }
    """

    qa_text = "\n".join(
        [
            f"{'INTERVIEWER' if c['speaker'] == 'agent' else 'CANDIDATE'}: {c['message']}"
            for c in conversation
        ]
    )

    try:

        messages = [

            SystemMessage(
                content=(
                    f"You are an expert technical interviewer.\n\n"

                    f"Generate a professional interview evaluation report.\n\n"

                    f"Candidate Information:\n"
                    f"- Name: {candidate['name']}\n"
                    f"- Role: {candidate['role']}\n"
                    f"- Experience: {candidate['experience']} years\n\n"

                    f"Evaluate:\n"
                    f"- technical skills\n"
                    f"- communication ability\n"
                    f"- conceptual understanding\n"
                    f"- confidence\n"
                    f"- problem-solving ability\n\n"

                    f"Respond ONLY with STRICT VALID JSON.\n\n"

                    f"DO NOT include:\n"
                    f"- markdown\n"
                    f"- explanations\n"
                    f"- code fences\n"
                    f"- extra text\n\n"

                    f"The JSON MUST contain ALL keys.\n\n"

                    f'Required JSON format:\n'
                    f'{{\n'
                    f'  "overall_score": 85,\n'
                    f'  "technical_score": 80,\n'
                    f'  "communication_score": 90,\n'
                    f'  "strengths": [\n'
                    f'    "Strong Python fundamentals"\n'
                    f'  ],\n'
                    f'  "improvements": [\n'
                    f'    "Needs deeper database optimization knowledge"\n'
                    f'  ],\n'
                    f'  "recommendation": "Selected"\n'
                    f'}}'
                )
            ),

            HumanMessage(
                content=(
                    f"Full Interview Transcript:\n\n"
                    f"{qa_text}"
                )
            ),
        ]

        response = _llm().invoke(messages)

        parsed = _parse_json(response.content)

        # ================================================================
        # SAFE SCHEMA ENFORCEMENT
        # ================================================================

        report = {

            "overall_score": parsed.get(
                "overall_score",
                0
            ),

            "technical_score": parsed.get(
                "technical_score",
                0
            ),

            "communication_score": parsed.get(
                "communication_score",
                0
            ),

            "strengths": parsed.get(
                "strengths",
                []
            ),

            "improvements": parsed.get(
                "improvements",
                []
            ),

            "recommendation": parsed.get(
                "recommendation",
                "On Hold"
            ),
        }

        return report

    except Exception as e:
        raise GroqAPIError(str(e))