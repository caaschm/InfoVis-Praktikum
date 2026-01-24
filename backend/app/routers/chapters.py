"""Chapter management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import re

from app.database import get_db
from app import models, schemas
from app.services.text_processor import split_into_sentences
from app.services.ai_client import generate_chapter_title

router = APIRouter(prefix="/api/documents/{document_id}/chapters", tags=["chapters"])


@router.post("/", response_model=schemas.ChapterBase, status_code=status.HTTP_201_CREATED)
def create_chapter(
    document_id: str,
    chapter: schemas.ChapterCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new chapter in a document.
    Supports different types: chapter, prologue, epilogue, interlude, foreword, afterword, custom.
    Auto-generates title if not provided based on type.
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
    
    # Determine chapter type
    chapter_type = chapter.type or "chapter"
    
    # Determine title based on type
    # IMPORTANT: Special sections (prologue, epilogue, etc.) should never be numbered
    special_section_types = ['prologue', 'epilogue', 'interlude', 'foreword', 'afterword', 'custom']
    
    if chapter_type == "custom":
        # Custom sections should never be numbered - use title exactly as provided
        if chapter.title:
            # Remove any numbers from the beginning of the title
            cleaned_title = re.sub(r'^\d+\s+', '', chapter.title).strip()
            title = cleaned_title or chapter.title
        else:
            title = "Custom Section"  # Default if no title provided
    elif chapter_type in special_section_types:
        # Special sections: remove any numbers from title if provided, or use default
        if chapter.title:
            # Remove any numbers from the beginning of the title
            cleaned_title = re.sub(r'^\d+\s+', '', chapter.title).strip()
            title = cleaned_title or chapter.title
        else:
            # Auto-generate title based on type
            if chapter_type == "prologue":
                title = "Prologue"
            elif chapter_type == "epilogue":
                title = "Epilogue"
            elif chapter_type == "interlude":
                title = "Interlude"
            elif chapter_type == "foreword":
                title = "Foreword"
            elif chapter_type == "afterword":
                title = "Afterword"
    elif chapter.title:
        # For chapters, use provided title (may contain numbers)
        title = chapter.title
    else:  # chapter
        # Count only numbered chapters for numbering
        numbered_chapters = [ch for ch in existing_chapters if ch.type == "chapter"]
        chapter_num = len(numbered_chapters) + 1
        title = f"Chapter {chapter_num}"
    
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
        type=chapter_type,
        emoji=chapter.emoji,
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
        type=getattr(db_chapter, 'type', 'chapter'),
        emoji=getattr(db_chapter, 'emoji', None),
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
            type=getattr(c, 'type', 'chapter'),
            emoji=getattr(c, 'emoji', None),
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
    """Update a chapter title, type, or emoji."""
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
    
    # Track type change for renumbering logic
    old_type = getattr(chapter, 'type', None) or 'chapter'
    new_type = chapter_update.type if chapter_update.type is not None else old_type
    type_changing = old_type != new_type
    
    # List of special section types that should not be numbered
    special_section_types = ['prologue', 'epilogue', 'interlude', 'foreword', 'afterword', 'custom']
    
    # Update fields if provided
    # IMPORTANT: Only chapters should have numbers - special sections should not
    if chapter_update.title is not None:
        current_type = chapter_update.type if chapter_update.type is not None else chapter.type
        if current_type == "custom":
            # Custom sections: use title exactly as provided (no numbering)
            chapter.title = chapter_update.title
        elif current_type != "chapter":
            # Special sections (prologue, epilogue, etc.): remove any numbers from title
            cleaned_title = re.sub(r'^\d+\s+', '', chapter_update.title).strip()
            chapter.title = cleaned_title or chapter_update.title
        else:
            # Chapters: use title as provided (may contain numbers)
            chapter.title = chapter_update.title
    if chapter_update.type is not None:
        chapter.type = chapter_update.type
    if chapter_update.emoji is not None:
        chapter.emoji = chapter_update.emoji
    
    # If type changed from "chapter" to any special section, renumber remaining chapters
    # This applies to: prologue, epilogue, interlude, foreword, afterword, custom
    if type_changing:
        db.flush()  # Ensure type change is visible
        
        # If changing FROM chapter TO any special section type, renumber remaining chapters
        if old_type == "chapter" and new_type in special_section_types:
            # Chapter was converted to a special section - renumber remaining chapters
            numbered_chapters = db.query(models.Chapter).filter(
                models.Chapter.document_id == document_id,
                models.Chapter.type == "chapter"
            ).order_by(models.Chapter.index).all()
            
            for idx, ch in enumerate(numbered_chapters, start=1):
                current_title = ch.title
                custom_part = ""
                # Try to extract custom title part (text after "Chapter X:" or "Chapter X " or just a number like "02 Title")
                # Pattern 1: "Chapter 2: Title" or "Chapter 2 Title"
                title_match = re.match(r'^Chapter\s+\d+\s*:?\s*(.+)$', current_title, re.IGNORECASE)
                if title_match:
                    custom_part = title_match.group(1).strip()
                else:
                    # Pattern 2: "02 Title" or "2 Title" (number at start)
                    title_match2 = re.match(r'^\d+\s+(.+)$', current_title)
                    if title_match2:
                        custom_part = title_match2.group(1).strip()
                
                if custom_part:
                    ch.title = f"Chapter {idx}: {custom_part}"
                else:
                    ch.title = f"Chapter {idx}"
            db.flush()
            for ch in numbered_chapters:
                db.refresh(ch)
        
        # If changing FROM any special section TO chapter, renumber all chapters
        elif old_type in special_section_types and new_type == "chapter":
            # Special section was converted to a chapter - renumber all chapters
            numbered_chapters = db.query(models.Chapter).filter(
                models.Chapter.document_id == document_id,
                models.Chapter.type == "chapter"
            ).order_by(models.Chapter.index).all()
            
            for idx, ch in enumerate(numbered_chapters, start=1):
                current_title = ch.title
                custom_part = ""
                # Try to extract custom title part (text after "Chapter X:" or "Chapter X " or just a number like "02 Title")
                # Pattern 1: "Chapter 2: Title" or "Chapter 2 Title"
                title_match = re.match(r'^Chapter\s+\d+\s*:?\s*(.+)$', current_title, re.IGNORECASE)
                if title_match:
                    custom_part = title_match.group(1).strip()
                else:
                    # Pattern 2: "02 Title" or "2 Title" (number at start)
                    title_match2 = re.match(r'^\d+\s+(.+)$', current_title)
                    if title_match2:
                        custom_part = title_match2.group(1).strip()
                
                if custom_part:
                    ch.title = f"Chapter {idx}: {custom_part}"
                else:
                    ch.title = f"Chapter {idx}"
            db.flush()
            for ch in numbered_chapters:
                db.refresh(ch)
    
    db.commit()
    db.refresh(chapter)
    
    return schemas.ChapterBase(
        id=chapter.id,
        document_id=chapter.document_id,
        title=chapter.title,
        type=getattr(chapter, 'type', 'chapter') or 'chapter',
        emoji=getattr(chapter, 'emoji', None),
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
    """
    Delete a chapter. Sentences in the chapter become unassigned.
    Automatically renumbers subsequent chapters to maintain sequential order.
    """
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
    
    # Get the index of the chapter being deleted
    deleted_index = chapter.index
    
    # Delete all sentences belonging to this chapter
    # This ensures they don't appear in "All Chapters" view after deletion
    sentences_to_delete = db.query(models.Sentence).filter(
        models.Sentence.chapter_id == chapter_id
    ).all()
    
    for sentence in sentences_to_delete:
        db.delete(sentence)
    
    # Delete chapter
    db.delete(chapter)
    db.flush()  # Flush deletion so subsequent queries don't see the deleted chapter
    
    # Renumber subsequent chapters (decrease index by 1)
    subsequent_chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id,
        models.Chapter.index > deleted_index
    ).all()
    
    for ch in subsequent_chapters:
        ch.index -= 1
    
    db.flush()  # Flush index changes before renumbering titles
    
    # If deleted chapter was a numbered chapter, renumber ALL remaining numbered chapters
    # This ensures Chapter 2 becomes Chapter 1, Chapter 3 becomes Chapter 2, etc.
    # IMPORTANT: This only applies to numbered chapters (type == "chapter"), not special sections
    deleted_type = getattr(chapter, 'type', None) or 'chapter'
    if deleted_type == "chapter":
        # Get all remaining numbered chapters, ordered by their index (after deletion and index adjustment)
        numbered_chapters = db.query(models.Chapter).filter(
            models.Chapter.document_id == document_id,
            models.Chapter.type == "chapter"
        ).order_by(models.Chapter.index).all()
        
        # Update titles to reflect new sequential numbering starting from 1
        # Chapter 2 becomes Chapter 1, Chapter 3 becomes Chapter 2, etc.
        for idx, ch in enumerate(numbered_chapters, start=1):
            # Preserve any custom title text after the chapter number if it exists
            current_title = ch.title
            custom_part = ""
            
            # Try to extract custom title part (text after "Chapter X:" or "Chapter X ")
            # Pattern matches: "Chapter 2", "Chapter 2: Title", "Chapter 2 Title", etc.
            title_match = re.match(r'^Chapter\s+(\d+)\s*:?\s*(.*)$', current_title, re.IGNORECASE)
            if title_match:
                # Check if there's a custom part after the number
                if len(title_match.groups()) > 1 and title_match.group(2).strip():
                    custom_part = title_match.group(2).strip()
            
            # Update title with new number, preserving custom part if it exists
            if custom_part:
                ch.title = f"Chapter {idx}: {custom_part}"
            else:
                ch.title = f"Chapter {idx}"
        
        # Flush the title changes
        db.flush()
    
    # Rebuild document content to reflect changes (deleted chapter's sentences are removed)
    all_remaining_chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    
    document_content_parts = []
    for ch in all_remaining_chapters:
        chapter_sentences = db.query(models.Sentence).filter(
            models.Sentence.chapter_id == ch.id
        ).order_by(models.Sentence.index).all()
        if chapter_sentences:
            chapter_text = ' '.join(s.text for s in chapter_sentences)
            document_content_parts.append(chapter_text)
    
    # Add unassigned sentences (if any exist - deleted chapter's sentences are removed, not unassigned)
    unassigned_sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id,
        models.Sentence.chapter_id.is_(None)
    ).order_by(models.Sentence.index).all()
    if unassigned_sentences:
        unassigned_text = ' '.join(s.text for s in unassigned_sentences)
        document_content_parts.append(unassigned_text)
    
    # Update document content (deleted chapter's sentences are removed, so they won't appear in "All Chapters")
    document.content = ' '.join(document_content_parts)
    
    db.commit()
    
    return None


@router.post("/reorder", status_code=status.HTTP_200_OK)
def reorder_chapters(
    document_id: str,
    reorder_request: schemas.ChapterReorderRequest,
    db: Session = Depends(get_db)
):
    """
    Reorder chapters by providing a list of chapter IDs in the desired order.
    Updates indices automatically.
    """
    chapter_order = reorder_request.chapter_ids
    
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all chapters for this document
    chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).all()
    
    # Create a mapping of chapter ID to chapter object
    chapter_map = {ch.id: ch for ch in chapters}
    
    # Verify all provided chapter IDs exist and belong to this document
    for chapter_id in chapter_order:
        if chapter_id not in chapter_map:
            raise HTTPException(status_code=400, detail=f"Chapter {chapter_id} not found")
    
    # Verify we have all chapters (no extras, no missing)
    if len(chapter_order) != len(chapters):
        raise HTTPException(
            status_code=400,
            detail=f"Chapter order must include all chapters. Expected {len(chapters)}, got {len(chapter_order)}"
        )
    
    # Update indices based on new order
    for new_index, chapter_id in enumerate(chapter_order):
        chapter_map[chapter_id].index = new_index
    
    # If any numbered chapters were reordered, update their titles
    numbered_chapters = [ch for ch in chapters if ch.type == "chapter"]
    if numbered_chapters:
        # Sort by new index
        numbered_chapters.sort(key=lambda ch: chapter_order.index(ch.id))
        # Update titles - preserve custom title parts
        for idx, ch in enumerate(numbered_chapters, start=1):
            current_title = ch.title
            custom_part = ""
            
            # Extract custom part from various formats:
            # - "Chapter 1: Title" or "Chapter 1 Title"
            # - "01 Title" or "1 Title"
            # - "01" (no custom part)
            
            # Try "Chapter X: Title" or "Chapter X Title" format
            chapter_match = re.match(r'^Chapter\s+\d+\s*:?\s*(.+)$', current_title, re.IGNORECASE)
            if chapter_match:
                custom_part = chapter_match.group(1).strip()
            else:
                # Try format like "01 Title" or "1 Title" or "01 Queen"
                num_match = re.match(r'^\d+\s+(.+)$', current_title)
                if num_match:
                    custom_part = num_match.group(1).strip()
                # If no match, title is just a number (e.g., "01"), so custom_part stays empty
            
            # Update title with new number, preserving custom part
            padded_num = str(idx).zfill(2)  # Zero-pad to 2 digits (01, 02, 03, etc.)
            if custom_part:
                ch.title = f"{padded_num} {custom_part}"
            else:
                ch.title = f"{padded_num}"
            
            # Debug logging
            print(f"Renumbering chapter {ch.id}: '{current_title}' -> '{ch.title}' (index: {ch.index} -> {idx})")
    
    db.flush()
    db.commit()
    
    return {"message": "Chapters reordered successfully"}


@router.post("/{chapter_id}/suggest-title", response_model=schemas.ChapterTitleSuggestion)
async def suggest_chapter_title(
    document_id: str,
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate an AI-suggested title for a chapter based on its content.
    """
    # Verify document and chapter exist
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chapter = db.query(models.Chapter).filter(
        models.Chapter.id == chapter_id,
        models.Chapter.document_id == document_id
    ).first()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get all sentences for this chapter
    sentences = db.query(models.Sentence).filter(
        models.Sentence.chapter_id == chapter_id
    ).order_by(models.Sentence.index).all()
    
    if not sentences:
        raise HTTPException(status_code=400, detail="Chapter has no content to analyze")
    
    # Combine all sentences into chapter content
    chapter_content = " ".join(s.text for s in sentences)
    
    # Generate title suggestion
    suggested_title = await generate_chapter_title(chapter_content, chapter.type or "chapter")
    
    return {"suggested_title": suggested_title}
