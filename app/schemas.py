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



class SessionCreateRequest(BaseModel):
    candidate_id: str

class InterviewStartRequest(BaseModel):
    session_id:   str
    interview_id: str

class AnswerSaveRequest(BaseModel):
    session_id:  str
    question_id: str
    answer_text: str

class NextQuestionRequest(BaseModel):
    session_id:        str
    previous_question: str
    candidate_answer:  str

class EndInterviewRequest(BaseModel):
    session_id: str

class ReportGenerateRequest(BaseModel):
    session_id: str



class STTRequest(BaseModel):
    session_id:   str
    interview_id: str
    question_id:  str
    audio_file:   str   # base64-encoded WAV/MP3

class TTSRequest(BaseModel):
    text:       str
    voice_type: str   = "female_en"
    speed:      float = 1.0



class ReflectionRequest(BaseModel):
    session_id:       str
    question:         str
    candidate_answer: str