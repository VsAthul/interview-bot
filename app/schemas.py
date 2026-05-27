# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional


class CandidateRegisterRequest(BaseModel):
    name:       str
    email:      EmailStr
    phone:      Optional[str] = None
    role:       str
    experience: int
    skillset:   List[str]


class InterviewRequest(BaseModel):
    session_id:  str
    answer:      Optional[str] = None
    question_id: Optional[str] = None
    end:         bool = False


class TTSRequest(BaseModel):
    text:       str
    voice_type: str   = "female_en"
    speed:      float = 1.0



class ReflectionRequest(BaseModel):
    session_id:       str
    question:         str
    candidate_answer: str