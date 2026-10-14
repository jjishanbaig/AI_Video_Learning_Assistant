from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now_utc(): return datetime.now(timezone.utc)

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), default="Untitled source")
    source_type: Mapped[str] = mapped_column(String(40), default="text")
    origin: Mapped[str] = mapped_column(String(1000), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="source", cascade="all, delete-orphan")

class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300), default="Generated material")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    source: Mapped[Source] = relationship(back_populates="artifacts")
