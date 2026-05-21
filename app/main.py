import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.exceptions import register_exception_handlers
from app.routers import candidate, interview, stt, tts, reflection

os.makedirs("audio", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Database ready")
    yield
    print("Shutting down")


app = FastAPI(
    title="AI Interview Bot",
    description="Voice-based automated technical interview system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/audio", StaticFiles(directory="audio"), name="audio")

templates = Jinja2Templates(directory = "templates")

@app.get("/", response_class = HTMLResponse)
async def ui(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
        )

register_exception_handlers(app)

app.include_router(candidate.router)
app.include_router(interview.router)
app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(reflection.router)

