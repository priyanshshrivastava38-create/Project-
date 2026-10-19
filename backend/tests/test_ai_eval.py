"""Runs the assistant evaluation dataset (tests/eval/assistant_eval.json) in deterministic mode
and reports per-case metrics: routing, grounding, required facts, citation correctness,
permission enforcement, insufficient-evidence handling and injection resistance."""

import json
import os

import pytest

from app.permissions.policy import Role
from app.services import documents

with open(os.path.join(os.path.dirname(__file__), "eval", "assistant_eval.json")) as fh:
    EVAL = json.load(fh)


@pytest.fixture()
def corpus(db):
    from app.models import User

    admin = db.query(User).filter_by(role="ADMIN").first()
    ids = {}
    for d in EVAL["documents"]:
        doc = documents.upload(
            db,
            admin,
            filename=f"{d['key']}.md",
            data=d["body"].encode(),
            title=d["title"],
            doc_type=d["type"],
            allowed_roles=d["roles"],
            document_id=None,
        )
        if d["approved"]:
            documents.approve(db, admin, doc.id, None, None)
        ids[d["key"]] = doc.id
    return ids


@pytest.mark.parametrize("case", EVAL["cases"], ids=[c["id"] for c in EVAL["cases"]])
def test_assistant_eval_case(case, corpus, as_role):
    r = as_role(Role(case["role"])).post("/assistant/chat", {"question": case["question"]})
    assert r.status_code == 200
    res = r.json()
    answer = res["answer"].lower()
    cited_docs = {c["document_id"] for c in res["citations"]}
    assert res["intent"] == case["intent"]
    if "grounded" in case:
        assert res["grounded"] is case["grounded"], res
    for fact in case.get("must_contain", []):
        assert fact.lower() in answer, f"missing '{fact}' in: {res['answer']}"
    for fact in case.get("must_not_contain", []):
        assert fact.lower() not in answer, f"leaked '{fact}' in: {res['answer']}"
    if cite := case.get("cite"):
        match = [c for c in res["citations"] if c["document_id"] == corpus[cite["doc"]]]
        assert match, f"expected citation of {cite['doc']}, got {res['citations']}"
        assert match[0]["section"] == cite["section"]
    for key in case.get("must_not_cite", []):
        assert corpus[key] not in cited_docs
    if prefix := case.get("answer_prefix"):
        assert res["answer"].startswith(prefix)
    # Every citation must point at a real, approved, role-visible document.
    for c in res["citations"]:
        assert c["document_id"] in corpus.values()
