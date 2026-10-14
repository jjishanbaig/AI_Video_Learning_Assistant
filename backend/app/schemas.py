from pydantic import BaseModel, Field
from typing import Literal

class YouTubeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    title: str | None = None

class TextSourceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=500000)
    source_type: Literal["text", "notes", "transcript"] = "notes"

class GenerateRequest(BaseModel):
    source_id: int
    style: str = "clear and structured"
    length: str = "detailed"

class ChatRequest(BaseModel):
    source_id: int
    question: str = Field(min_length=1, max_length=8000)
    history: list[dict] = []

class QuizRequest(BaseModel):
    source_id: int
    count: int = Field(default=8, ge=3, le=25)
    difficulty: str = "mixed"

class FlashcardRequest(BaseModel):
    source_id: int
    count: int = Field(default=12, ge=3, le=40)

class InterviewStartRequest(BaseModel):
    source_id: int
    difficulty: str = "intermediate"
    interview_type: str = "technical"
    question_count: int = Field(default=5, ge=3, le=15)

class InterviewAnswerRequest(BaseModel):
    source_id: int
    question: str
    answer: str
    difficulty: str = "intermediate"
