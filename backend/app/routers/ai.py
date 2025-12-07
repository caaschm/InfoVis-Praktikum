"""AI-powered endpoints for emoji and text generation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services.ai_client import (
    generate_emojis_for_sentence, 
    generate_text_from_emojis,
    get_character_emoji_mappings,
    clear_character_emoji_mappings,
    analyze_spider_chart_values,
    generate_spider_intent,
)

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


@router.get("/character-emoji-mappings")
async def get_character_mappings():
    """
    🎭 Get current character-emoji consistency mappings.
    
    Returns a dictionary showing which emojis are assigned to which characters.
    This ensures the same character always gets the same emoji across sentences.
    """
    mappings = get_character_emoji_mappings()
    return {"mappings": mappings, "count": len(mappings)}


@router.post("/clear-character-mappings")
async def clear_character_mappings():
    """
    🎭 Clear character-emoji consistency cache.
    
    Call this when switching to a new document or starting fresh.
    This allows characters in different stories to get different emojis.
    """
    clear_character_emoji_mappings()
    return {"status": "cleared", "message": "Character-emoji mappings cleared"}


@router.post("/analyze-spider-chart", response_model=schemas.SpiderChartAnalysisResponse)
async def analyze_spider_chart(
    request: schemas.SpiderChartAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze text and return spider chart values (drama, humor, conflict, mystery).
    Can analyze full document or selected text portion.
    """
    # Verify document exists
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Analyze text using AI service
    try:
        values = await analyze_spider_chart_values(request.text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze text: {str(e)}"
        )
    
    return schemas.SpiderChartAnalysisResponse(
        drama=values["drama"],
        humor=values["humor"],
        conflict=values["conflict"],
        mystery=values["mystery"]
    )


@router.post("/spider-intent", response_model=schemas.SpiderChartIntentResponse)
async def spider_intent(
        request: schemas.SpiderChartIntentRequest,
        db: Session = Depends(get_db)
):
    # Optional: check document exists
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        result = await generate_spider_intent(
            text=request.text,
            dimension=request.dimension,
            baseline=request.baseline_value,
            current=request.current_value,
        )
        return result
    except Exception as e:
        print("❌ Error generating spider intent:", e)
        raise HTTPException(status_code=500, detail="AI intent generation failed.")
