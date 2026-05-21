# app/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse



class CandidateNotFoundError(Exception):
    def __init__(self, candidate_id: str):
        self.candidate_id = candidate_id

class SessionNotFoundError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id

class DuplicateEmailError(Exception):
    def __init__(self, email: str):
        self.email = email

class InterviewAlreadyActiveError(Exception):
    pass

class InterviewNotActiveError(Exception):
    pass

class SarvamAPIError(Exception):
    def __init__(self, message: str):
        self.message = message

class GroqAPIError(Exception):
    def __init__(self, message: str):
        self.message = message

class AudioDecodeError(Exception):
    pass


# ── Register all handlers on the FastAPI app ─────────────────────────────────

def register_exception_handlers(app: FastAPI):

    @app.exception_handler(CandidateNotFoundError)
    async def _(req: Request, exc: CandidateNotFoundError):
        return JSONResponse(status_code=404,
            content={"success": False,
                     "error": f"Candidate '{exc.candidate_id}' not found"})

    @app.exception_handler(SessionNotFoundError)
    async def _(req: Request, exc: SessionNotFoundError):
        return JSONResponse(status_code=404,
            content={"success": False,
                     "error": f"Session '{exc.session_id}' not found"})

    @app.exception_handler(DuplicateEmailError)
    async def _(req: Request, exc: DuplicateEmailError):
        return JSONResponse(status_code=409,
            content={"success": False,
                     "error": f"Email '{exc.email}' is already registered"})

    @app.exception_handler(InterviewAlreadyActiveError)
    async def _(req: Request, exc: InterviewAlreadyActiveError):
        return JSONResponse(status_code=409,
            content={"success": False,
                     "error": "An interview session is already active for this candidate"})

    @app.exception_handler(InterviewNotActiveError)
    async def _(req: Request, exc: InterviewNotActiveError):
        return JSONResponse(status_code=400,
            content={"success": False,
                     "error": "Interview session is not active"})

    @app.exception_handler(SarvamAPIError)
    async def _(req: Request, exc: SarvamAPIError):
        return JSONResponse(status_code=502,
            content={"success": False,
                     "error": f"Sarvam API error: {exc.message}"})

    @app.exception_handler(GroqAPIError)
    async def _(req: Request, exc: GroqAPIError):
        return JSONResponse(status_code=502,
            content={"success": False,
                     "error": f"Groq LLM error: {exc.message}"})

    @app.exception_handler(AudioDecodeError)
    async def _(req: Request, exc: AudioDecodeError):
        return JSONResponse(status_code=400,
            content={"success": False,
                     "error": "Invalid audio data — could not decode base64"})

    @app.exception_handler(Exception)
    async def _(req: Request, exc: Exception):
        return JSONResponse(status_code=500,
            content={"success": False,
                     "error": "Internal server error",
                     "detail": str(exc)})