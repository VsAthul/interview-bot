from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.database import get_db
from app.services.sarvam_stt import transcribe_audio

router = APIRouter(prefix="/api/stt", tags=["STT"])


@router.post("/transcribe")
async def transcribe(
    audio_file: UploadFile = File(...),
    session_id: str = Form(...),
    question_id: str = Form(...),
):
    audio_bytes = await audio_file.read()
    result = await transcribe_audio(audio_bytes)
    return {"success": True, **result}