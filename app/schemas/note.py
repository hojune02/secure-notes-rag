from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)


class NoteOut(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True
