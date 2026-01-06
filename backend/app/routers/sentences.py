"""Sentence management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/sentences", tags=["sentences"])


@router.get("/{sentence_id}", response_model=schemas.SentenceResponse)
def get_sentence(sentence_id: str, db: Session = Depends(get_db)):
    """Get a single sentence with its character references."""
    sentence = db.query(models.Sentence).filter(models.Sentence.id == sentence_id).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    character_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
    emojis = json.loads(sentence.emojis) if sentence.emojis else []
    emoji_mappings = json.loads(sentence.emoji_mappings) if sentence.emoji_mappings else None
    
    return schemas.SentenceResponse(
        id=sentence.id,
        document_id=sentence.document_id,
        index=sentence.index,
        text=sentence.text,
        emojis=emojis,
        character_refs=character_refs,
        emoji_mappings=emoji_mappings
    )


@router.patch("/{sentence_id}", response_model=schemas.SentenceResponse)
def update_sentence(
    sentence_id: str,
    update: schemas.SentenceUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a sentence's text, emojis, and/or character references.
    
    Supports HYBRID emoji system:
    - emojis: Raw emoji strings (free generation)
    - character_refs: Character IDs (structured, normalized)
    """
    sentence = db.query(models.Sentence).filter(models.Sentence.id == sentence_id).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Update text if provided
    if update.text is not None:
        sentence.text = update.text
    
    # Update raw emojis if provided
    if update.emojis is not None:
        sentence.emojis = json.dumps(update.emojis)
    
    # Update character references if provided
    if update.character_refs is not None:
        sentence.character_refs = json.dumps(update.character_refs)
    
    # Update parent document's updated_at timestamp
    document = db.query(models.Document).filter(
        models.Document.id == sentence.document_id
    ).first()
    if document:
        from datetime import datetime, timezone
        document.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(sentence)
    
    emojis = json.loads(sentence.emojis) if sentence.emojis else []
    character_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
    emoji_mappings = json.loads(sentence.emoji_mappings) if sentence.emoji_mappings else None
    
    return schemas.SentenceResponse(
        id=sentence.id,
        document_id=sentence.document_id,
        index=sentence.index,
        text=sentence.text,
        emojis=emojis,
        character_refs=character_refs,
        emoji_mappings=emoji_mappings
    )
