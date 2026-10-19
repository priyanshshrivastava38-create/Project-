"""Rule-based intent routing. Transparent and testable; no LLM is involved in deciding
which database query runs."""

import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    name: str
    params: dict = field(default_factory=dict)


ORDER_RE = re.compile(r"\bSO-?(\d{3,})\b", re.I)
JOB_RE = re.compile(r"\bJOB-?(\d{3,})\b", re.I)


def classify(question: str) -> Intent:
    q = question.lower()
    if m := ORDER_RE.search(question):
        return Intent("order_status", {"order_number": f"SO-{m.group(1)}"})
    if m := JOB_RE.search(question):
        return Intent("job_status", {"job_number": f"JOB-{m.group(1)}"})
    if re.search(r"(below|under|low).{0,30}(reorder|stock)|low[- ]stock|reorder level|running low|out of stock", q):
        return Intent("low_stock")
    if re.search(r"overdue|late|behind schedule|past (their |the )?(target|due)", q) and re.search(
        r"job|production|work order", q
    ):
        return Intent("overdue_jobs")
    if re.search(r"(wait|await|pending|need).{0,30}(quality|inspection|qc)", q):
        return Intent("awaiting_inspection")
    if re.search(r"(ready|eligible).{0,20}(dispatch|ship|deliver)|in transit", q):
        return Intent("ready_for_dispatch")
    return Intent("documents")
