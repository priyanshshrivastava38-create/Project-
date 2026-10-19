"""Approved-document retrieval with BM25 (rank-bm25).

Only chunks of the *currently approved* version of documents the user's role may see are
indexed. The index is built per query; that is fast enough for an SME document library
(thousands of chunks) and means approval/visibility changes take effect immediately.
"""

import math
import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentVersion, User
from app.models.enums import DocumentStatus
from app.services.documents import can_view

STOPWORDS = set(
    """a an and are as at be by can do does for from has have how i in is it its me my of on or our please say says tell
    that the their them there these this to us was we what when where which who why will with you your about summarize
    summarise summary approved document documents doc procedure according many much must should""".split()
)
SUFFIXES = ("ically", "ally", "ation", "ing", "ed", "es", "s", "ly", "al")
MIN_OVERLAP_RATIO = 0.3  # share of distinct query terms a passage must contain
RELATIVE_CUTOFF = 0.35  # drop passages scoring far below the best hit


def stem(token: str) -> str:
    """Very light suffix stripping so 'checked'/'check', 'batches'/'batch', 'dimensional'/'dimensionally' match."""
    if token[0].isdigit():
        return token
    for suf in SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def tokenize(text: str) -> list[str]:
    # Hyphenated words are split ("quality-control" -> quality, control); decimals like 0.5 stay whole.
    return [stem(t) for t in re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", text.lower()) if t not in STOPWORDS and len(t) > 1]


@dataclass
class Passage:
    chunk_id: int
    document_id: int
    document_title: str
    version_number: int
    page_number: int | None
    section: str | None
    text: str
    score: float


def retrieve(db: Session, user: User, question: str, k: int = 4) -> list[Passage]:
    q_tokens = tokenize(question)
    if not q_tokens:
        return []
    rows = (
        db.execute(
            select(DocumentChunk, DocumentVersion, Document)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(DocumentVersion.status == DocumentStatus.APPROVED, Document.status == DocumentStatus.APPROVED)
        )
        .unique()
        .all()
    )
    rows = [r for r in rows if can_view(user, r[2])]
    if not rows:
        return []
    corpus = [tokenize(f"{doc.title} {chunk.section or ''} {chunk.text}") for chunk, _, doc in rows]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(q_tokens)
    q_set = set(q_tokens)
    need = max(1, math.ceil(MIN_OVERLAP_RATIO * len(q_set)))
    overlap = [len(q_set & set(doc_tokens)) for doc_tokens in corpus]
    # BM25 IDF can be <= 0 for terms present in most chunks of a tiny corpus, so eligibility is
    # decided by term overlap and BM25 is used for ordering.
    candidates = [i for i in range(len(rows)) if overlap[i] >= need]
    if not candidates:
        return []
    ranked = sorted(candidates, key=lambda i: (scores[i], overlap[i]), reverse=True)
    top = scores[ranked[0]]
    out = []
    for i in ranked:
        if top > 0 and scores[i] < top * RELATIVE_CUTOFF:
            continue
        chunk, ver, doc = rows[i]
        out.append(
            Passage(
                chunk.id, doc.id, doc.title, ver.version_number, chunk.page_number, chunk.section, chunk.text, float(scores[i])
            )
        )
        if len(out) >= k:
            break
    return out
