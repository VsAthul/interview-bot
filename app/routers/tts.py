from fastapi import APIRouter
from app.schemas import TTSRequest
from app.services.sarvam_tts import text_to_speech

router = APIRouter(prefix="/api/tts", tags=["TTS"])


@router.post("/generate")
async def generate_tts(data: TTSRequest):
    audio_url = await text_to_speech(data.text, data.voice_type, data.speed)
    return {"success": True, "audio_url": audio_url}