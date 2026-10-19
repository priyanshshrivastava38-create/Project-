from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.ai.assistant import answer
from app.ai.providers import get_provider
from app.core.deps import DB, require
from app.models import AssistantQuery, User
from app.permissions.policy import P
from app.schemas.assistant import ChatRequest, ChatResponse

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: DB, user: User = Depends(require(P.ASSISTANT_USE))):
    """Answer from permission-checked business data or approved documents, with citations.
    Works without any LLM configured (deterministic mode)."""
    return answer(db, user, body.question)


@router.get("/history")
def history(db: DB, user: User = Depends(require(P.ASSISTANT_USE))) -> list[dict]:
    """The caller's own recent questions (never other users')."""
    rows = db.execute(
        select(AssistantQuery).where(AssistantQuery.user_id == user.id).order_by(AssistantQuery.id.desc()).limit(20)
    ).scalars()
    return [
        {"id": r.id, "question": r.question, "answer": r.answer, "intent": r.intent, "created_at": r.created_at} for r in rows
    ]


@router.get("/health")
def health(_: User = Depends(require(P.ASSISTANT_USE))) -> dict:
    p = get_provider()
    return {"provider": p.name, "llm_configured": p.name != "deterministic", "retrieval": "bm25"}
