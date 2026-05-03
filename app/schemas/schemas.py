# app/schemas/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    message: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    created_at: datetime


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"
    document_ids: list[str] = []


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    document_ids: list[str]
    created_at: datetime


class MessageCreate(BaseModel):
    content: str


class SourceResponse(BaseModel):
    filename: str
    chunk_index: int
    content_preview: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict]
    created_at: datetime


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str
    reformulated_question: Optional[str] = None
