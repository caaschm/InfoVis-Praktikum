"""Sentence management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/sentences", tags=["sentences"])


@router.get("/{sentence_id}", response_model=schemas.SentenceResponse)
def get_sentence(sentence_id: str, db: Session = Depends(get_db)):
    """Get a single sentence with its emojis."""
    sentence = db.query(models.Sentence).filter(models.Sentence.id == sentence_id).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Get emojis
    emoji_tags = db.query(models.EmojiTag).filter(
        models.EmojiTag.sentence_id == sentence_id
    ).order_by(models.EmojiTag.position).all()
    
    emojis = [tag.emoji for tag in emoji_tags]
    
    return schemas.SentenceResponse(
        id=sentence.id,
        document_id=sentence.document_id,
        index=sentence.index,
        text=sentence.text,
        emojis=emojis
    )


@router.patch("/{sentence_id}", response_model=schemas.SentenceResponse)
def update_sentence(
    sentence_id: str,
    update: schemas.SentenceUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a sentence's text, emojis, and/or chapter assignment.
    Max 5 emojis enforced via schema validation.
    """
    sentence = db.query(models.Sentence).filter(models.Sentence.id == sentence_id).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Update text if provided
    if update.text is not None:
        sentence.text = update.text
    
    # Update chapter_id if provided
    if update.chapter_id is not None:
        # Verify chapter exists if provided (allow None to unassign)
        if update.chapter_id:
            chapter = db.query(models.Chapter).filter(
                models.Chapter.id == update.chapter_id
            ).first()
            if not chapter:
                raise HTTPException(status_code=404, detail="Chapter not found")
        sentence.chapter_id = update.chapter_id
    
    # Update emojis if provided
    if update.emojis is not None:
        # Delete existing emoji tags
        db.query(models.EmojiTag).filter(
            models.EmojiTag.sentence_id == sentence_id
        ).delete()
        
        # Create new emoji tags
        for position, emoji in enumerate(update.emojis[:5]):  # Enforce max 5
            emoji_tag = models.EmojiTag(
                sentence_id=sentence_id,
                position=position,
                emoji=emoji
            )
            db.add(emoji_tag)
    
    # Update parent document's updated_at timestamp
    document = db.query(models.Document).filter(
        models.Document.id == sentence.document_id
    ).first()
    if document:
        from datetime import datetime, timezone
        document.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(sentence)
    
    # Get updated emojis
    emoji_tags = db.query(models.EmojiTag).filter(
        models.EmojiTag.sentence_id == sentence_id
    ).order_by(models.EmojiTag.position).all()
    
    emojis = [tag.emoji for tag in emoji_tags]
    
    return schemas.SentenceResponse(
        id=sentence.id,
        document_id=sentence.document_id,
        chapter_id=sentence.chapter_id,  # Include chapter_id in response
        index=sentence.index,
        text=sentence.text,
        emojis=emojis
    )
