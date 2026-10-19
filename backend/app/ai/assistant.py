"""MetalFlow Assistant orchestration.

1. validate + authorize (route dependency requires assistant:use)
2. classify intent (rules)
3. business data -> permission-checked read-only tool; deterministic answer (no LLM needed)
4. documents -> BM25 over approved, role-visible chunks
5. build numbered context; call LLM if configured
6. validate citations (only numbers that exist in the context survive); fall back to an
   extractive answer if the LLM fails, cites nothing valid, or reports insufficient evidence
7. log the interaction
"""

import logging
import re
import time

from sqlalchemy.orm import Session

from app.ai import data_tools, intents, retrieval
from app.ai.providers import AIProvider, ProviderError, get_provider
from app.models import AssistantQuery, User
from app.permissions.policy import has_permission

logger = logging.getLogger("metalflow.ai")
INSUFFICIENT = "I cannot verify an answer to that from approved company documents or the business data available to your role."


def _excerpt(text: str, n: int = 320) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def _ref(p: retrieval.Passage) -> str:
    loc = f"p. {p.page_number}" if p.page_number else (f"§ {p.section}" if p.section else "")
    return f"{p.document_title} v{p.version_number}" + (f", {loc}" if loc else "")


def build_context(passages: list[retrieval.Passage]) -> str:
    return "\n\n".join(f"[{i}] ({_ref(p)})\n<<<\n{p.text}\n>>>" for i, p in enumerate(passages, start=1))


def validate_citations(answer: str, n_sources: int) -> tuple[str, list[int]]:
    """Remove citation markers that do not refer to a provided source; return used ids."""
    used: list[int] = []

    def repl(m: re.Match) -> str:
        k = int(m.group(1))
        if 1 <= k <= n_sources:
            if k not in used:
                used.append(k)
            return m.group(0)
        return ""

    cleaned = re.sub(r"\[(\d{1,3})\]", repl, answer)
    return cleaned.strip(), used


# Sentences that address the reader/assistant with instructions are never repeated verbatim.
INJECTION_RE = re.compile(
    r"ignore (all |any )?(previous|prior|above|earlier)|disregard (the |all |your )|system (override|prompt)|"
    r"you are now|reveal (the |your )?(password|secret|prompt|key)|act as|new instructions",
    re.I,
)


def relevant_sentences(text: str, question: str, limit: int = 2) -> tuple[list[str], bool]:
    """Return the sentences of a passage most related to the question, and whether any were withheld."""
    q = set(retrieval.tokenize(question))
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip() and not x.strip().startswith("#")]
    withheld = any(INJECTION_RE.search(x) for x in sentences)
    safe = [x for x in sentences if not INJECTION_RE.search(x)]
    scored = sorted(((len(q & set(retrieval.tokenize(x))), i, x) for i, x in enumerate(safe)), key=lambda t: (-t[0], t[1]))
    picked = sorted((i, x) for score, i, x in scored[:limit] if score > 0) or [(0, safe[0])] if safe else []
    return [_excerpt(x, 240) for _, x in picked], withheld


def extractive_answer(passages: list[retrieval.Passage], question: str = "") -> tuple[str, list[int]]:
    """Deterministic answer: the most relevant sentences of the top passages, each cited."""
    parts, used, withheld_any = [], [], False
    for i, p in enumerate(passages[:3], start=1):
        sents, withheld = relevant_sentences(p.text, question)
        withheld_any |= withheld
        if sents:
            parts.append(" ".join(sents) + f" [{i}]")
            used.append(i)
    text = "From approved documents: " + " ".join(parts) if parts else INSUFFICIENT
    if withheld_any:
        text += " (Some text in the source looked like instructions to the assistant and was not repeated.)"
    return text, used


def answer(db: Session, user: User, question: str, provider: AIProvider | None = None) -> dict:
    started = time.monotonic()
    provider = provider or get_provider()
    intent = intents.classify(question)
    result = {
        "answer": INSUFFICIENT,
        "intent": intent.name,
        "source_type": "none",
        "citations": [],
        "facts": [],
        "provider": "deterministic",
        "fallback_used": False,
        "grounded": False,
    }

    if intent.name in data_tools.TOOLS:
        permission, area, tool = data_tools.TOOLS[intent.name]
        if not has_permission(user.role, permission):
            result["answer"] = f"Your role ({user.role}) does not have access to {area} data, so I can't answer that."
            result["intent"] = f"{intent.name}:denied"
        else:
            tr = tool(db, intent.params)
            result.update(
                answer=tr.answer, source_type="database", grounded=tr.found, facts=[{"label": k, "value": v} for k, v in tr.facts]
            )
    else:
        passages = retrieval.retrieve(db, user, question)
        if passages:
            text, used = None, []
            if provider.name != "deterministic":
                try:
                    raw = provider.generate_answer(build_context(passages), question)
                    if "INSUFFICIENT_EVIDENCE" not in raw:
                        text, used = validate_citations(raw, len(passages))
                        if not used:
                            text = None  # uncited LLM output is not accepted as grounded
                    result["provider"] = provider.name
                except ProviderError as e:
                    logger.warning("LLM provider unavailable, using extractive fallback: %s", e)
                if text is None:
                    result["fallback_used"] = True
            if text is None:
                text, used = extractive_answer(passages, question)
            result.update(answer=text, source_type="documents", grounded=bool(used))
            result["citations"] = [
                {
                    "id": k,
                    "document_id": passages[k - 1].document_id,
                    "document_title": passages[k - 1].document_title,
                    "version_number": passages[k - 1].version_number,
                    "page_number": passages[k - 1].page_number,
                    "section": passages[k - 1].section,
                    "excerpt": _excerpt(passages[k - 1].text),
                }
                for k in used
            ]

    latency = int((time.monotonic() - started) * 1000)
    db.add(
        AssistantQuery(
            user_id=user.id,
            question=question[:1000],
            intent=result["intent"],
            answer=result["answer"][:4000],
            citations=[
                {"document_id": c["document_id"], "page": c["page_number"], "section": c["section"]} for c in result["citations"]
            ],
            provider=result["provider"],
            fallback_used=result["fallback_used"],
            latency_ms=latency,
        )
    )
    db.commit()
    return result
