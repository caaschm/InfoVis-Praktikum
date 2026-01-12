"""Chapter management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.services.text_processor import split_into_sentences

router = APIRouter(prefix="/api/documents/{document_id}/chapters", tags=["chapters"])


@router.post("/", response_model=schemas.ChapterBase, status_code=status.HTTP_201_CREATED)
def create_chapter(
    document_id: str,
    chapter: schemas.ChapterCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new chapter in a document.
    Auto-generates chapter number (01, 02, etc.) if title not provided.
    If no chapters exist, inserts at beginning. Otherwise appends after last chapter.
    If sentences exist without a chapter, assigns them to the first created chapter.
    """
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get existing chapters to determine next number and position
    existing_chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    
    # Determine chapter number and title
    if chapter.title:
        # Use provided title, but ensure it has numbering
        title = chapter.title
    else:
        # Auto-generate title with number
        chapter_num = len(existing_chapters) + 1
        title = f"{chapter_num:02d} Title"
    
    # Determine index (insert at beginning if no chapters, otherwise append)
    if len(existing_chapters) == 0:
        new_index = 0
        # Assign all existing unassigned sentences to this first chapter
        unassigned_sentences = db.query(models.Sentence).filter(
            models.Sentence.document_id == document_id,
            models.Sentence.chapter_id.is_(None)
        ).all()
        for sentence in unassigned_sentences:
            # Will update after chapter is created
            pass
    else:
        # Append after last chapter
        new_index = existing_chapters[-1].index + 1
    
    # Create chapter
    db_chapter = models.Chapter(
        document_id=document_id,
        title=title,
        index=new_index
    )
    db.add(db_chapter)
    db.flush()  # Get the chapter ID
    
    # If this is the first chapter, assign all unassigned sentences to it
    has_unassigned_sentences = False
    if len(existing_chapters) == 0:
        unassigned_sentences = db.query(models.Sentence).filter(
            models.Sentence.document_id == document_id,
            models.Sentence.chapter_id.is_(None)
        ).all()
        if unassigned_sentences:
            has_unassigned_sentences = True
            for sentence in unassigned_sentences:
                sentence.chapter_id = db_chapter.id
        db.flush()  # Ensure sentences are updated before commit
    
    # Add default initial text ONLY if chapter has no sentences (new chapter, not first with existing text)
    if not has_unassigned_sentences:
        DEFAULT_CHAPTER_TEXT = (
            "Once upon a time in a distant land, a brave hero embarked on an epic journey. "
            "The hero traveled through dark forests and crossed raging rivers. "
            "In a mysterious castle, the hero discovered an ancient treasure. "
            "A fierce dragon guarded the treasure with flames and fury. "
            "The hero fought bravely against the dragon in an epic battle. "
            "Magic filled the air as the hero cast powerful spells. "
            "A wise wizard appeared and offered guidance to the hero. "
            "The dragon finally retreated into the shadows of the castle. "
            "The hero claimed the treasure and became a legend. "
            "The kingdom celebrated the hero with a grand festival."
        )
        
        # Create sentences from default text and assign to this chapter
        default_sentences = split_into_sentences(DEFAULT_CHAPTER_TEXT)
        
        # Get the highest sentence index in the document to append new sentences
        max_sentence_index = db.query(models.Sentence).filter(
            models.Sentence.document_id == document_id
        ).order_by(models.Sentence.index.desc()).first()
        
        start_index = (max_sentence_index.index + 1) if max_sentence_index else 0
        
        # Create sentence records for the default text
        for idx, sentence_text in enumerate(default_sentences):
            db_sentence = models.Sentence(
                document_id=document_id,
                chapter_id=db_chapter.id,
                index=start_index + idx,
                text=sentence_text
            )
            db.add(db_sentence)
        db.flush()  # Ensure sentences are added before updating document content
    
    # Update document content to include the new chapter's text
    # Get all sentences ordered by chapter index and sentence index
    all_chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    
    document_content_parts = []
    for ch in all_chapters:
        chapter_sentences = db.query(models.Sentence).filter(
            models.Sentence.chapter_id == ch.id
        ).order_by(models.Sentence.index).all()
        if chapter_sentences:
            chapter_text = ' '.join(s.text for s in chapter_sentences)
            document_content_parts.append(chapter_text)
    
    # Add unassigned sentences
    unassigned_sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id,
        models.Sentence.chapter_id.is_(None)
    ).order_by(models.Sentence.index).all()
    if unassigned_sentences:
        unassigned_text = ' '.join(s.text for s in unassigned_sentences)
        document_content_parts.append(unassigned_text)
    
    # Update document content
    document.content = ' '.join(document_content_parts)
    
    db.flush()  # Ensure all changes are flushed
    db.commit()
    db.refresh(db_chapter)
    
    return schemas.ChapterBase(
        id=db_chapter.id,
        document_id=db_chapter.document_id,
        title=db_chapter.title,
        index=db_chapter.index,
        created_at=db_chapter.created_at,
        updated_at=db_chapter.updated_at
    )


@router.get("/", response_model=List[schemas.ChapterBase])
def list_chapters(document_id: str, db: Session = Depends(get_db)):
    """List all chapters for a document."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    
    return [
        schemas.ChapterBase(
            id=c.id,
            document_id=c.document_id,
            title=c.title,
            index=c.index,
            created_at=c.created_at,
            updated_at=c.updated_at
        ) for c in chapters
    ]


@router.patch("/{chapter_id}", response_model=schemas.ChapterBase)
def update_chapter(
    document_id: str,
    chapter_id: str,
    chapter_update: schemas.ChapterUpdate,
    db: Session = Depends(get_db)
):
    """Update a chapter title."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Verify chapter exists
    chapter = db.query(models.Chapter).filter(
        models.Chapter.id == chapter_id,
        models.Chapter.document_id == document_id
    ).first()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Update title if provided
    if chapter_update.title is not None:
        chapter.title = chapter_update.title
    
    db.commit()
    db.refresh(chapter)
    
    return schemas.ChapterBase(
        id=chapter.id,
        document_id=chapter.document_id,
        title=chapter.title,
        index=chapter.index,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    document_id: str,
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """Delete a chapter. Sentences in the chapter become unassigned."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Verify chapter exists
    chapter = db.query(models.Chapter).filter(
        models.Chapter.id == chapter_id,
        models.Chapter.document_id == document_id
    ).first()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Unassign sentences from this chapter
    db.query(models.Sentence).filter(
        models.Sentence.chapter_id == chapter_id
    ).update({models.Sentence.chapter_id: None})
    
    # Delete chapter
    db.delete(chapter)
    db.commit()
    
    return None
