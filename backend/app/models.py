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
    """Sentence model - individual sentence within a document.
    
    Supports HYBRID emoji system:
    - emojis: Raw emoji strings (FREE generation, no structure)
    - character_refs: Character IDs (STRUCTURED generation, normalized)
    
    Workflow: generate emojis freely → define characters → normalize to character_refs
    """
    __tablename__ = "sentences"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    index = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)
    emojis = Column(Text, nullable=True)  # JSON array of raw emoji strings (unstructured)
    character_refs = Column(Text, nullable=True)  # JSON array of character IDs (structured)

    # Relationships
    document = relationship("Document", back_populates="sentences")


class Character(Base):
    """Character/Subject definition - SINGLE SOURCE OF TRUTH for emojis.
    
    All emoji rendering, highlighting, and AI generation derives from this model.
    When a character's emoji changes, all text automatically re-renders.
    """
    __tablename__ = "characters"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    name = Column(String, nullable=False)  # Primary name (e.g., "Hero", "Dark Forest")
    emoji = Column(String, nullable=False)  # Emoji representation (e.g., "👑", "🌲")
    color = Column(String, nullable=False)  # Hex color for text highlighting (e.g., "#FF5733")
    aliases = Column(Text, nullable=True)  # JSON array of alternative names/mentions
    description = Column(Text, nullable=True)  # Optional notes about the character/subject
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship
    document = relationship("Document", backref="characters")
