"""AI-powered endpoints for emoji and text generation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services.ai_client import generate_emojis_for_sentence, generate_text_from_emojis

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/emojis-from-text", response_model=schemas.EmojiSuggestionResponse)
async def suggest_emojis_from_text(
    request: schemas.EmojiSuggestionRequest,
    db: Session = Depends(get_db)
):
    """
    Generate emoji suggestions from sentence text.
    Uses together.ai to analyze mood/plot and suggest up to 5 emojis.
    
    TODO: Fine-tune prompt engineering for better emoji selection.
    """
    # Verify sentence exists
    sentence = db.query(models.Sentence).filter(
        models.Sentence.id == request.sentence_id
    ).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Generate emojis using AI service
    try:
        emojis = await generate_emojis_for_sentence(request.text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate emojis: {str(e)}"
        )
    
    return schemas.EmojiSuggestionResponse(
        sentence_id=request.sentence_id,
        emojis=emojis
    )


@router.post("/text-from-emojis", response_model=schemas.TextFromEmojisResponse)
async def suggest_text_from_emojis(
    request: schemas.TextFromEmojisRequest,
    db: Session = Depends(get_db)
):
    """
    Generate text suggestions from emojis.
    Uses together.ai to create 1-2 sentences matching the emoji mood/plot.
    
    TODO: Fine-tune prompt engineering for better text generation.
    Consider adding more context from surrounding sentences.
    """
    # Verify document exists
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # If sentence_id provided, verify it exists and get context
    context = None
    if request.sentence_id:
        sentence = db.query(models.Sentence).filter(
            models.Sentence.id == request.sentence_id
        ).first()
        
        if not sentence:
            raise HTTPException(status_code=404, detail="Sentence not found")
        
        # TODO: Build better context from surrounding sentences
        # For now, just use the document title as minimal context
        context = f"Story: {document.title}"
    
    # Generate text using AI service
    try:
        suggested_text = await generate_text_from_emojis(
            emojis=request.emojis,
            context=context
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate text: {str(e)}"
        )
    
    return schemas.TextFromEmojisResponse(
        sentence_id=request.sentence_id,
        suggested_text=suggested_text
    )
