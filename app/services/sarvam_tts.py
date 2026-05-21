# import base64
# import os
# import uuid
# import httpx
# from app.config import settings
# from app.exceptions import SarvamAPIError

# SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
# AUDIO_DIR = "audio"


# async def text_to_speech(text: str, voice_type: str = "female_en", speed: float = 1.0) -> str:
#     speaker = "meera" if voice_type == "female_en" else "arjun"

#     try:
#         async with httpx.AsyncClient(timeout=30) as client:
#             response = await client.post(
#                 SARVAM_TTS_URL,
#                 headers={
#                     "api-subscription-key": settings.sarvam_api_key,
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "inputs": [text],
#                     "target_language_code": "en-IN",
#                     "speaker": speaker,
#                     "pitch": 0,
#                     "pace": speed,
#                     "loudness": 1.5,
#                     "speech_sample_rate": 22050,
#                     "enable_preprocessing": True,
#                     "model": "bulbul:v1",
#                 },
#             )
#             print("Sarvam Status:", response.status_code)
#             print("Sarvam Response:", response.text)

#             if response.status_code != 200:
#                 raise SarvamAPIError(
#                     f"HTTP {response.status_code}: {response.text}"
#                 )
#             data = response.json()
#             audio_b64 = data["audios"][0]

#             os.makedirs(AUDIO_DIR, exist_ok=True)
#             filename = f"audio_{uuid.uuid4().hex[:8]}.wav"
#             filepath = os.path.join(AUDIO_DIR, filename)
#             with open(filepath, "wb") as f:
#                 f.write(base64.b64decode(audio_b64))

#             return f"/{AUDIO_DIR}/{filename}"

#     except SarvamAPIError:
#         raise
#     except Exception as e:
#         raise SarvamAPIError(str(e))

import base64
import os
import uuid
import httpx
from app.config import settings
from app.exceptions import SarvamAPIError

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
AUDIO_DIR = "audio"


async def text_to_speech(
    text: str,
    voice_type: str = "female_en",
    speed: float = 1.0
) -> str:

    speaker = "priya" if voice_type == "female_en" else "rahul"
    try:
        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                SARVAM_TTS_URL,
                headers={
                    "api-subscription-key": settings.sarvam_api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "inputs": [text],
                    "target_language_code": "en-IN",
                    "speaker": speaker,
                    "pace": speed,
                    "model": "bulbul:v3",
                },
            )

            print("========== SARVAM TTS ==========")
            print("Status:", response.status_code)

            if response.status_code != 200:
                raise SarvamAPIError(
                    f"HTTP {response.status_code}: {response.text}"
                )

            data = response.json()

            audio_b64 = data["audios"][0]

            os.makedirs(AUDIO_DIR, exist_ok=True)

            filename = f"audio_{uuid.uuid4().hex[:8]}.wav"

            filepath = os.path.join(AUDIO_DIR, filename)

            with open(filepath, "wb") as f:
                f.write(base64.b64decode(audio_b64))

            return f"/audio/{filename}"

    except Exception as e:
        raise SarvamAPIError(str(e))