from fastapi import APIRouter, Depends
from app.database import get_db
from app.schemas import STTRequest
from app.services.sarvam_stt import transcribe_audio

router = APIRouter(prefix="/api/stt", tags=["STT"])


@router.post("/transcribe")
async def transcribe(data: STTRequest):
    result = await transcribe_audio(data.audio_file)
    return {"success": True, **result}