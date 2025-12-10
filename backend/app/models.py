"""SQLAlchemy database models."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


def generate_uuid():
    """Generate UUID string."""
    return str(uuid.uuid4())


class Document(Base):
    """Document model - represents a story/chapter."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to sentences
    sentences = relationship("Sentence", back_populates="document", cascade="all, delete-orphan")


class Sentence(Base):
    """Sentence model - individual sentence within a document."""
    __tablename__ = "sentences"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    index = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="sentences")
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


class WordEmojiMapping(Base):
    """Word-level emoji mapping - associates specific words/phrases with emojis."""
    __tablename__ = "word_emoji_mappings"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    word_pattern = Column(String, nullable=False)  # The word/phrase to match (case-insensitive)
    emoji = Column(String, nullable=False)  # The emoji to associate
    is_active = Column(Integer, default=1)  # Boolean flag to enable/disable mapping
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CustomEmojiSet(Base):
    """Custom emoji collection for a document - author's curated emoji palette."""
    __tablename__ = "custom_emoji_sets"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g., "Fantasy Elements", "Character Emotions"
    emojis = Column(Text, nullable=False)  # JSON array of emoji strings
    is_default = Column(Integer, default=0)  # Whether this is the default set for quick access
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CharacterDefinition(Base):
    """Character/subject definition with associated emoji and metadata."""
    __tablename__ = "character_definitions"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    name = Column(String, nullable=False)  # Character/subject name
    emoji = Column(String, nullable=False)  # Primary emoji representation
    aliases = Column(Text, nullable=True)  # JSON array of alternative names/references
    description = Column(Text, nullable=True)  # Optional description
    color = Column(String, nullable=True)  # Hex color for highlighting (e.g., "#FF5733")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
