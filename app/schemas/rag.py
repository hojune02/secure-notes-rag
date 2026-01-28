from pydantic import BaseModel, Field
from uuid import UUID


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    score: float
    snippet: str


class RagQueryResponse(BaseModel):
    answer: str
    citations: list[RagCitation]


class RagUploadResponse(BaseModel):
    document_id: UUID
    num_chunks: int
    filename: str
