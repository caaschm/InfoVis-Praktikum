"""Document management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.services.text_processor import split_into_sentences

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/", response_model=schemas.DocumentDetail, status_code=status.HTTP_201_CREATED)
def create_document(
    document: schemas.DocumentCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new document from uploaded/pasted text.
    Automatically splits content into sentences.
    """
    # Create document
    db_document = models.Document(
        title=document.title,
        content=document.content
    )
    db.add(db_document)
    db.flush()  # Get the document ID
    
    # Split content into sentences
    sentences = split_into_sentences(document.content)
    
    # Create sentence records
    for index, sentence_text in enumerate(sentences):
        db_sentence = models.Sentence(
            document_id=db_document.id,
            index=index,
            text=sentence_text
        )
        db.add(db_sentence)
    
    db.commit()
    db.refresh(db_document)
    
    # Build response with sentences and emojis
    return _build_document_detail(db_document, db)


@router.get("/", response_model=List[schemas.DocumentMetadata])
def list_documents(db: Session = Depends(get_db)):
    """List all documents with minimal metadata."""
    documents = db.query(models.Document).order_by(models.Document.updated_at.desc()).all()
    return documents


@router.get("/{document_id}", response_model=schemas.DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a document with all sentences and emojis."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return _build_document_detail(document, db)


@router.patch("/{document_id}", response_model=schemas.DocumentDetail)
def update_document_content(
    document_id: str,
    content_update: schemas.DocumentContentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update document content and re-parse sentences.
    Preserves emojis by matching sentences by text content.
    """
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update content
    document.content = content_update.content
    
    # Get existing sentences with their emojis
    existing_sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    ).all()
    
    # Create a map of sentence text to emojis
    emoji_map = {}
    for sent in existing_sentences:
        emojis = db.query(models.EmojiTag).filter(
            models.EmojiTag.sentence_id == sent.id
        ).all()
        emoji_map[sent.text.strip()] = [e.emoji for e in emojis]
    
    # Delete existing sentences and emojis (cascade will handle emojis)
    db.query(models.Sentence).filter(models.Sentence.document_id == document_id).delete()
    
    # Split new content into sentences
    sentences = split_into_sentences(content_update.content)
    
    # Create new sentence records, preserving emojis where text matches
    for index, sentence_text in enumerate(sentences):
        db_sentence = models.Sentence(
            document_id=document.id,
            index=index,
            text=sentence_text
        )
        db.add(db_sentence)
        db.flush()  # Get the new sentence ID
        
        # Restore emojis if this sentence text existed before
        if sentence_text.strip() in emoji_map:
            for emoji in emoji_map[sentence_text.strip()]:
                db_emoji = models.EmojiTag(
                    sentence_id=db_sentence.id,
                    emoji=emoji
                )
                db.add(db_emoji)
    
    db.commit()
    db.refresh(document)
    
    return _build_document_detail(document, db)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return _build_document_detail(document, db)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document and all associated sentences/emojis."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(document)
    db.commit()
    
    return None


# Helper function
def _build_document_detail(document: models.Document, db: Session) -> schemas.DocumentDetail:
    """Build DocumentDetail response with sentences and emojis."""
    sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document.id
    ).order_by(models.Sentence.index).all()
    
    sentence_responses = []
    for sentence in sentences:
        # Get emojis for this sentence
        emoji_tags = db.query(models.EmojiTag).filter(
            models.EmojiTag.sentence_id == sentence.id
        ).order_by(models.EmojiTag.position).all()
        
        emojis = [tag.emoji for tag in emoji_tags]
        
        sentence_responses.append(schemas.SentenceBase(
            id=sentence.id,
            document_id=sentence.document_id,
            index=sentence.index,
            text=sentence.text,
            emojis=emojis
        ))
    
    return schemas.DocumentDetail(
        id=document.id,
        title=document.title,
        content=document.content,
        created_at=document.created_at,
        updated_at=document.updated_at,
        sentences=sentence_responses
    )
