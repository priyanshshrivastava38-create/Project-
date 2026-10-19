from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class Citation(BaseModel):
    id: int
    document_id: int
    document_title: str
    version_number: int
    page_number: int | None
    section: str | None
    excerpt: str


class DataFact(BaseModel):
    label: str
    value: str


class ChatResponse(BaseModel):
    answer: str
    intent: str
    source_type: str  # database | documents | none
    citations: list[Citation]
    facts: list[DataFact]
    provider: str
    fallback_used: bool
    grounded: bool
