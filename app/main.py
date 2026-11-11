"""FastAPI backend for the CMTI help-desk chatbot.

Endpoints (see /docs when running):
  POST /api/chat                 send session_id + message; returns reply, latency_ms, message_id
  GET  /api/history/{session_id} past messages in a session
  POST /api/feedback             thumbs up/down for a bot message
  POST /api/reset/{session_id}   start a new conversation
  GET  /api/health               status check for the hosting platform
The chat page is served at / and the embeddable widget at /widget.js and /widget.css.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.config import settings
from app.llm import ChatError, complete
from app.prompt import build_messages

WEB = Path(__file__).resolve().parent.parent / "web"

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="CMTI Help Desk Chatbot", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(default="", max_length=5000)


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int = Field(description="+1 for thumbs up, -1 for thumbs down")


@app.exception_handler(ChatError)
def _chat_error(_, exc: ChatError):
    return JSONResponse(status_code=exc.status, content={"error": exc.user_message})


@app.post("/api/chat")
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "Please type a question before sending.")
    if len(message) > settings.max_message_chars:
        raise HTTPException(400, f"Please keep your message under {settings.max_message_chars} characters.")

    session_id = db.ensure_session(req.session_id)
    history = db.get_history(session_id, limit=settings.history_turns * 2)
    reply, latency_ms, tokens = complete(build_messages(history, message))
    # Store only after a successful reply, so failed attempts don't pollute the memory.
    db.add_message(session_id, "user", message)
    message_id = db.add_message(session_id, "bot", reply, latency_ms, tokens)
    return {"session_id": session_id, "reply": reply, "latency_ms": latency_ms, "tokens_used": tokens, "message_id": message_id}


@app.get("/api/history/{session_id}")
def history(session_id: str):
    return {"session_id": session_id, "messages": db.get_history(session_id)}


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    if req.rating not in (1, -1):
        raise HTTPException(400, "Rating must be 1 or -1.")
    if not db.message_exists(req.message_id):
        raise HTTPException(404, "Message not found.")
    db.save_feedback(req.message_id, req.rating)
    return {"ok": True}


@app.post("/api/reset/{session_id}")
def reset(session_id: str):
    # Old messages stay in the log for analysis; the user simply continues in a fresh session.
    return {"session_id": db.ensure_session(None)}


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.model, "configured": bool(settings.openai_api_key)}


@app.exception_handler(HTTPException)
def _http_error(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
