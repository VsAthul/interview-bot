import base64
import httpx
from app.config import settings
from app.exceptions import SarvamAPIError, AudioDecodeError

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"


async def transcribe_audio(audio_base64: str) -> dict:
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception:
        raise AudioDecodeError()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": settings.sarvam_api_key},
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                data={"model": "saarika:v2.5", "language_code": "en-IN"},
            )
            if response.status_code != 200:
                raise SarvamAPIError(f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            return {
                "answer_text": data.get("transcript", ""),
                "confidence_score": data.get("confidence", 0.0),
            }
    except SarvamAPIError:
        raise
    except Exception as e:
        raise SarvamAPIError(str(e))