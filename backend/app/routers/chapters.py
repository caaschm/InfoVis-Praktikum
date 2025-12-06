"""Chapter management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/chapters", tags=["chapters"])


@router.post("/", response_model=schemas.ChapterBase, status_code=status.HTTP_201_CREATED)
def create_chapter(
    chapter: schemas.ChapterCreate,
    db: Session = Depends(get_db)
):
    """Create a new chapter in a document."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == chapter.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the next index
    existing_chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == chapter.document_id
    ).order_by(models.Chapter.index.desc()).first()
    
    next_index = (existing_chapters.index + 1) if existing_chapters else 0
    
    # Create chapter
    db_chapter = models.Chapter(
        document_id=chapter.document_id,
        title=chapter.title,
        index=next_index
    )
    db.add(db_chapter)
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


@router.get("/document/{document_id}", response_model=List[schemas.ChapterBase])
def list_chapters(document_id: str, db: Session = Depends(get_db)):
    """List all chapters for a document."""
    chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    return chapters


@router.patch("/{chapter_id}", response_model=schemas.ChapterBase)
def update_chapter(
    chapter_id: str,
    chapter_update: schemas.ChapterUpdate,
    db: Session = Depends(get_db)
):
    """Update a chapter."""
    chapter = db.query(models.Chapter).filter(models.Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
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
def delete_chapter(chapter_id: str, db: Session = Depends(get_db)):
    """Delete a chapter and all associated sentences."""
    chapter = db.query(models.Chapter).filter(models.Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    db.delete(chapter)
    db.commit()
    return None
