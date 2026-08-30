"""
FastAPI Chat Endpoint — Phase 6
---------------------------------
Exposes the Orchestrator as a multi-turn HTTP API.

Endpoints:
  POST /chat   — ask a question, get an answer (or clarification request)
  GET  /health — liveness probe

Design notes:
- Multi-turn: client sends conversation history; it's passed to the
  Orchestrator's synthesis LLM so answers are context-aware.
- Graceful error handling: Monday/Groq failures → HTTP 503 with
  human-readable message; Pydantic validation → HTTP 422.
- CORS enabled for all origins (frontend may be on a different domain).
- Static files (frontend/) served at / so this is a self-contained app.
"""

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from src.config import config
from src.orchestrator import Orchestrator, OrchestratorError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Skylark Drones BI Agent",
    description="Natural-language BI agent over live Monday.com data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-init orchestrator (avoids startup crash if .env missing on cold start)
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        config.validate()
        _orchestrator = Orchestrator()
    return _orchestrator


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str          # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    clarification_needed: bool
    clarification_question: Optional[str]
    data_quality_notes: List[str]
    query_plan: dict
    partial_failure: bool
    partial_failure_reason: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness probe — returns 200 + version immediately."""
    return {"status": "ok", "version": "1.0.0", "service": "skylark-bi-agent"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Main chat endpoint. Accepts a question + conversation history,
    returns an answer or a clarification request.
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    # Convert Pydantic ChatMessage list to plain dicts for the orchestrator
    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        orch = get_orchestrator()
        result = orch.answer(question=req.question.strip(), history=history)
    except EnvironmentError as e:
        logger.error("Config error: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Service configuration error: {e}. Please contact the administrator.",
        )
    except OrchestratorError as e:
        logger.error("Orchestrator error: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"The BI agent encountered an error: {e}. Please try again.",
        )
    except Exception as e:
        logger.exception("Unexpected error in /chat: %s", e)
        raise HTTPException(
            status_code=503,
            detail="An unexpected error occurred. Please try again in a moment.",
        )

    return ChatResponse(
        answer=result.answer,
        clarification_needed=result.clarification_needed,
        clarification_question=result.clarification_question,
        data_quality_notes=result.data_quality_notes,
        query_plan=result.query_plan,
        partial_failure=result.partial_failure,
        partial_failure_reason=result.partial_failure_reason,
    )


# ---------------------------------------------------------------------------
# Static file serving (frontend)
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
