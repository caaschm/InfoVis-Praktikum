"""SQLAlchemy database models."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


def generate_uuid():
    """Generate UUID string."""
    return str(uuid.uuid4())

class Chapter(Base):
    """Chapter model - represents a chapter within a document."""
    __tablename__ = "chapters"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    title = Column(String, nullable=False)
    index = Column(Integer, nullable=False)  # Order within document
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="chapters")
    sentences = relationship("Sentence", back_populates="chapter", cascade="all, delete-orphan")


class Document(Base):
    """Document model - represents a story/chapter."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

   # Relationships
    chapters = relationship("Chapter", back_populates="document", cascade="all, delete-orphan", order_by="Chapter.index")
    sentences = relationship("Sentence", back_populates="document", cascade="all, delete-orphan")  # Keep for backward compatibility

class Sentence(Base):
    """Sentence model - individual sentence within a document."""
    __tablename__ = "sentences"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True)  # Make nullable for migration
    index = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="sentences")
    chapter = relationship("Chapter", back_populates="sentences")
    emoji_tags = relationship("EmojiTag", back_populates="sentence", cascade="all, delete-orphan")


class EmojiTag(Base):
    """Emoji tag model - emojis attached to sentences (max 5 per sentence)."""
    __tablename__ = "emoji_tags"

    id = Column(String, primary_key=True, default=generate_uuid)
    sentence_id = Column(String, ForeignKey("sentences.id"), nullable=False)
    position = Column(Integer, nullable=False)  # Position 0-4 (max 5 emojis)
    emoji = Column(String, nullable=False)  # The emoji character(s)

    # Relationship
    sentence = relationship("Sentence", back_populates="emoji_tags")
