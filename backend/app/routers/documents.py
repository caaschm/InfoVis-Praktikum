"""Document management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import io
import json

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


@router.post("/upload-pdf", response_model=schemas.DocumentDetail, status_code=status.HTTP_201_CREATED)
async def upload_pdf_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    📄 Upload a PDF or TXT file and create a document.
    Extracts text from PDF using pypdf2 (if available) or treats as text file.
    """
    # Determine title from filename if not provided
    if not title:
        title = file.filename.rsplit('.', 1)[0] if file.filename else "Untitled"
    
    # Read file content
    content_bytes = await file.read()
    
    # Try to extract text based on file type
    if file.filename and file.filename.lower().endswith('.pdf'):
        try:
            # Try to import PyPDF2
            from PyPDF2 import PdfReader
            
            # Parse PDF
            pdf_file = io.BytesIO(content_bytes)
            pdf_reader = PdfReader(pdf_file)
            
            # Extract text from all pages
            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
            
            content = '\n'.join(text_parts)
            
            if not content.strip():
                raise HTTPException(
                    status_code=400,
                    detail="PDF appears to be empty or contains only images"
                )
                
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="PDF processing not available. Install pypdf2: pip install pypdf2"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse PDF: {str(e)}"
            )
    else:
        # Treat as text file
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('latin-1')
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to decode file as text. Please ensure it's a valid text file."
                )
    
    # Create document using the extracted content
    db_document = models.Document(
        title=title,
        content=content
    )
    db.add(db_document)
    db.flush()
    
    # Split content into sentences
    sentences = split_into_sentences(content)
    
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
    
    # Get existing sentences with their emojis, character_refs, and chapter assignments
    existing_sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    ).order_by(models.Sentence.index).all()
    
    # Create a map of sentence text to preserved data (emojis, character_refs, chapter_id)
    # Use a list to handle multiple sentences with same text but different chapters
    sentence_data_list = []
    for sent in existing_sentences:
        # Parse JSON arrays from database
        emojis = json.loads(sent.emojis) if sent.emojis else []
        character_refs = json.loads(sent.character_refs) if sent.character_refs else []
        sentence_data_list.append({
            'text': sent.text.strip(),
            'emojis': emojis,
            'character_refs': character_refs,
            'chapter_id': sent.chapter_id,
            'index': sent.index
        })
    
    # Delete existing sentences
    db.query(models.Sentence).filter(models.Sentence.document_id == document_id).delete()
    
    # Split new content into sentences
    new_sentences = split_into_sentences(content_update.content)
    
    # Get chapters ordered by index to help with chapter assignment
    chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document_id
    ).order_by(models.Chapter.index).all()
    
    # Create new sentence records, preserving emojis, character_refs, and chapter_id where text matches
    used_sentence_indices = set()
    assigned_chapters = []  # Track chapter assignments for new sentences to infer from context
    
    for index, sentence_text in enumerate(new_sentences):
        sentence_text_stripped = sentence_text.strip()
        
        # Try to find matching sentence by text and position
        preserved_data = None
        
        # First, try exact match by text and index
        if index < len(sentence_data_list):
            candidate = sentence_data_list[index]
            if candidate['text'] == sentence_text_stripped:
                preserved_data = candidate
                used_sentence_indices.add(index)
        
        # If no match, try to find by text only (but prefer unused ones)
        if not preserved_data:
            for i, candidate in enumerate(sentence_data_list):
                if candidate['text'] == sentence_text_stripped and i not in used_sentence_indices:
                    preserved_data = candidate
                    used_sentence_indices.add(i)
                    break
        
        # Determine chapter_id
        chapter_id = None
        if preserved_data:
            # Use preserved chapter_id from matching sentence
            chapter_id = preserved_data.get('chapter_id')
        else:
            # For new sentences, infer chapter from nearby assigned sentences in the NEW list
            # Look at previous sentences that were already processed and assigned
            if index > 0 and len(assigned_chapters) > 0:
                # Use the chapter of the most recent previous sentence
                chapter_id = assigned_chapters[-1]
            elif chapters:
                # Fallback: assign to first chapter if exists
                chapter_id = chapters[0].id
        
        # Track assigned chapter for context inference (for next iteration)
        if chapter_id:
            assigned_chapters.append(chapter_id)
            # Keep only last 10 for context
            if len(assigned_chapters) > 10:
                assigned_chapters = assigned_chapters[-10:]
        
        db_sentence = models.Sentence(
            document_id=document.id,
            index=index,
            text=sentence_text,
            chapter_id=chapter_id,
            emojis=json.dumps(preserved_data.get('emojis', [])) if preserved_data and preserved_data.get('emojis') else None,
            character_refs=json.dumps(preserved_data.get('character_refs', [])) if preserved_data and preserved_data.get('character_refs') else None
        )
        db.add(db_sentence)
    
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
    """Build DocumentDetail response with sentences and characters."""
    import json
    
    sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document.id
    ).order_by(models.Sentence.index).all()
    
    sentence_responses = []
    for sentence in sentences:
        # Parse character references and emojis from JSON
        character_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        emoji_mappings = json.loads(sentence.emoji_mappings) if sentence.emoji_mappings else None
        
        sentence_responses.append(schemas.SentenceBase(
            id=sentence.id,
            document_id=sentence.document_id,
            chapter_id=sentence.chapter_id,
            index=sentence.index,
            text=sentence.text,
            emojis=emojis,
            character_refs=character_refs,
            emoji_mappings=emoji_mappings
        ))
    
    # Get all characters for this document (SINGLE SOURCE OF TRUTH)
    characters = db.query(models.Character).filter(
        models.Character.document_id == document.id
    ).order_by(models.Character.created_at).all()
    
    character_responses = [
        schemas.CharacterResponse(
            id=c.id,
            document_id=c.document_id,
            name=c.name,
            emoji=c.emoji,
            color=c.color,
            aliases=json.loads(c.aliases) if c.aliases else [],
            description=c.description,
            word_phrases=json.loads(c.word_phrases) if c.word_phrases and c.word_phrases != 'null' else [],
            created_at=c.created_at
        ) for c in characters
    ]
    
    # Get all chapters for this document
    chapters = db.query(models.Chapter).filter(
        models.Chapter.document_id == document.id
    ).order_by(models.Chapter.index).all()
    
    chapter_responses = [
        schemas.ChapterBase(
            id=ch.id,
            document_id=ch.document_id,
            title=ch.title,
            type=getattr(ch, 'type', 'chapter'),
            emoji=getattr(ch, 'emoji', None),
            index=ch.index,
            created_at=ch.created_at,
            updated_at=ch.updated_at
        ) for ch in chapters
    ]
    
    return schemas.DocumentDetail(
        id=document.id,
        title=document.title,
        content=document.content,
        created_at=document.created_at,
        updated_at=document.updated_at,
        sentences=sentence_responses,
        characters=character_responses,
        chapters=chapter_responses
    )


@router.post("/{document_id}/merge-emojis")
def merge_emojis(
    document_id: str,
    request: schemas.MergeEmojisRequest,
    db: Session = Depends(get_db)
):
    """
    Merge two emojis - replace all occurrences of source_emoji with target_emoji
    across all sentences in the document.
    """
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all sentences in this document
    sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    ).all()
    
    updated_count = 0
    
    for sentence in sentences:
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        
        # Replace source emoji with target emoji
        if request.source_emoji in emojis:
            # Remove source emoji
            emojis = [e for e in emojis if e != request.source_emoji]
            # Add target emoji if not already present
            if request.target_emoji not in emojis:
                emojis.append(request.target_emoji)
            
            sentence.emojis = json.dumps(emojis)
            updated_count += 1
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Merged {request.source_emoji} into {request.target_emoji}",
        "sentences_updated": updated_count
    }
