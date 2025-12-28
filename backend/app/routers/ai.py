"""AI-powered endpoints for character suggestion and text generation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import re

from app.database import get_db
from app import models, schemas
from app.services import ai_client
from app.services.ai_client import generate_spider_intent, generate_story_arc, generate_sentence_stage_mapping

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Common function words to ignore when generating emojis
IGNORE_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'nor', 'for', 'yet', 'so',
    'at', 'by', 'for', 'from', 'in', 'into', 'of', 'on', 'to', 'with',
    'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did',
    'this', 'that', 'these', 'those',
    'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'my', 'your', 'his', 'her', 'its', 'our', 'their'
}


@router.post("/generate-emojis", response_model=schemas.CharacterSuggestionResponse)
async def generate_emojis_freely(
    request: schemas.CharacterSuggestionRequest,
    db: Session = Depends(get_db)
):
    """
    Generate emojis freely based on text content, WITHOUT requiring predefined characters.
    
    This is the PRIMARY generation endpoint for initial emoji assignment.
    - Analyzes semantic content (ignores function words)
    - Assigns emojis based on context
    - If characters are defined, uses them; otherwise generates freely
    - Updates emoji dictionary automatically
    
    TODO: Implement AI-powered emoji generation.
    """
    # Verify sentence exists
    sentence = db.query(models.Sentence).filter(
        models.Sentence.id == request.sentence_id
    ).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Get document to access existing characters
    document = db.query(models.Document).filter(
        models.Document.id == sentence.document_id
    ).first()
    
    # Load all existing characters for this document
    all_characters = []
    if document:
        all_characters = db.query(models.Character).filter(
            models.Character.document_id == document.id
        ).all()
    
    # If characters are defined in request, use character-based suggestion
    if request.characters and len(request.characters) > 0:
        return await suggest_characters_for_text(request, db)
    
    # Otherwise, generate emojis freely based on semantic content
    # TODO: Replace with real AI emoji generation
    
    # Simple placeholder: Extract meaningful words and assign emojis
    text_lower = request.text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Filter out common function words
    meaningful_words = [w for w in words if w not in IGNORE_WORDS]
    
    # STEP 1: Check if any existing characters are mentioned in this sentence
    character_refs = []
    character_word_mappings = {}
    
    for char in all_characters:
        char_name_lower = char.name.lower()
        
        # Check if character name appears as a whole word in text
        if re.search(r'\b' + re.escape(char_name_lower) + r'\b', text_lower):
            character_word_mappings[char_name_lower] = char.emoji
            if char.id not in character_refs:
                character_refs.append(char.id)
    
    # STEP 2: Use AI to generate emojis for the sentence
    # Pass character mappings so AI knows to use specific emojis for defined characters
    suggested_emojis, emoji_word_mappings = await ai_client.generate_emojis_for_sentence(
        text=request.text,
        word_mappings=character_word_mappings
    )
    
    # Save emojis and mappings to sentence
    sentence.emojis = json.dumps(suggested_emojis)
    sentence.character_refs = json.dumps(character_refs)
    sentence.emoji_mappings = json.dumps(emoji_word_mappings) if emoji_word_mappings else None
    db.commit()
    
    # Return emojis with character refs if any matched
    return schemas.CharacterSuggestionResponse(
        sentence_id=request.sentence_id,
        emojis=suggested_emojis,
        character_refs=character_refs
    )


@router.post("/suggest-characters", response_model=schemas.CharacterSuggestionResponse)
async def suggest_characters_for_text(
    request: schemas.CharacterSuggestionRequest,
    db: Session = Depends(get_db)
):
    """
    Suggest emojis for text - works with or without predefined characters.
    
    - If characters are defined: Uses them for structured generation
    - If no characters: Generates emojis freely based on semantic content
    
    Uses AI to generate contextual emojis.
    """
    # Verify sentence exists
    sentence = db.query(models.Sentence).filter(
        models.Sentence.id == request.sentence_id
    ).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # If no characters defined, delegate to generate-emojis endpoint
    if not request.characters or len(request.characters) == 0:
        return await generate_emojis_freely(request, db)
    
    # Character-based generation mode (HYBRID: characters + AI-generated emojis)
    text_lower = request.text.lower()
    
    suggested_refs = []
    character_word_mappings = {}
    matched_character_names = set()
    
    # First pass: Match characters by name/aliases
    for character in request.characters:
        # Check if character name appears as whole word in text
        name_lower = character['name'].lower()
        if re.search(r'\b' + re.escape(name_lower) + r'\b', text_lower):
            suggested_refs.append(character['id'])
            character_word_mappings[name_lower] = character['emoji']
            matched_character_names.add(name_lower)
            continue
        
        # Check aliases
        for alias in character.get('aliases', []):
            alias_lower = alias.lower()
            if re.search(r'\b' + re.escape(alias_lower) + r'\b', text_lower):
                suggested_refs.append(character['id'])
                character_word_mappings[alias_lower] = character['emoji']
                matched_character_names.add(name_lower)
                break
    
    # Use AI to generate emojis, passing character mappings so AI respects them
    suggested_emojis, emoji_word_mappings = await ai_client.generate_emojis_for_sentence(
        text=request.text,
        word_mappings=character_word_mappings
    )
    
    # Save results to sentence
    sentence.emojis = json.dumps(suggested_emojis)
    sentence.character_refs = json.dumps(suggested_refs)
    sentence.emoji_mappings = json.dumps(emoji_word_mappings) if emoji_word_mappings else None
    db.commit()
    
    return schemas.CharacterSuggestionResponse(
        sentence_id=request.sentence_id,
        emojis=suggested_emojis,
        character_refs=suggested_refs
    )


@router.post("/text-from-characters", response_model=schemas.TextFromCharactersResponse)
async def generate_text_from_characters(
    request: schemas.TextFromCharactersRequest,
    db: Session = Depends(get_db)
):
    """
    Generate text based on selected characters/subjects.
    
    Uses character context to create narratively appropriate text.
    TODO: Implement character-aware text generation with AI.
    """
    # For now, return a placeholder
    # TODO: Implement AI text generation using character context
    character_names = [c['name'] for c in request.characters if c['id'] in request.character_ids]
    
    suggested_text = f"A story involving {', '.join(character_names)}..."
    
    return schemas.TextFromCharactersResponse(
        sentence_id=request.sentence_id,
        suggested_text=suggested_text
    )



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
        values = await ai_client.analyze_spider_chart_values(request.text)
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

@router.post("/story-arc", response_model=schemas.StoryArcResponse)
async def compute_story_arc(
    request: schemas.StoryArcRequest,
    db: Session = Depends(get_db)
):
    """
    Compute a story arc (array of tension values + key beats) for the provided text.
    If document_id is provided and text is empty, use document content/title as fallback.
    """
    text = request.text
    if request.document_id and not text:
        document = db.query(models.Document).filter(
            models.Document.id == request.document_id
        ).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        # Minimal fallback: use title + body if available
        text = (document.title or "") + "\n\n" + (document.body or "")

    if not text:
        raise HTTPException(status_code=400, detail="No text provided for story arc analysis")

    try:
        result = await generate_story_arc(text=text, granularity=request.granularity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute story arc: {e}")

    # If we have a document, try to map beats to nearest sentence indices and ask AI to classify sentences
    sentence_classifications = []
    stage_values = []
    if request.document_id:
        sentences = db.query(models.Sentence).filter(models.Sentence.document_id == request.document_id).order_by(models.Sentence.index).all()
        if sentences and len(sentences) > 0:
            N = len(sentences)
            # Map beats positions to nearest sentence index and attach ids
            beats = result.get("beats", [])
            for b in beats:
                pos = float(b.get("position", 0)) if isinstance(b, dict) else getattr(b, 'position', 0)
                si = int(round(pos * (N - 1)))
                b["sentence_index"] = si
                b["sentence_id"] = sentences[si].id

            # Ask AI to classify each sentence into stages (best-effort)
            try:
                texts = [s.text for s in sentences]
                classifications = await generate_sentence_stage_mapping(text, texts)
            except Exception as e:
                print("❌ Error classifying sentences:", e)
                classifications = []

            # Build index->classification map
            cls_map = {c["index"]: c for c in classifications if isinstance(c, dict) and c.get("index") is not None}

            # Prepare to sample arc values if AI didn't provide numeric tension per sentence
            arc = result.get("arc", [])
            G = len(arc) if arc else request.granularity or 10

            def sample_arc_at_pos(pos: float) -> float:
                if not arc:
                    return 0.5
                pos = max(0.0, min(1.0, pos))
                fpos = pos * (G - 1)
                lo = int(fpos)
                hi = min(lo + 1, G - 1)
                t = fpos - lo
                return (1 - t) * arc[lo] + t * arc[hi]

            sentence_classifications = []
            for i, s in enumerate(sentences):
                if i in cls_map:
                    item = cls_map[i]
                    val = item.get("value")
                    if val is None:
                        pos = i / max(1, N - 1)
                        val = sample_arc_at_pos(pos)
                    sentence_classifications.append({"index": i, "stage": item.get("stage"), "value": float(val)})
                else:
                    # fallback stage by position
                    pos = i / max(1, N - 1)
                    if pos < 0.2:
                        stage = "Exposition"
                    elif pos < 0.55:
                        stage = "Rising Action"
                    elif pos < 0.7:
                        stage = "Climax"
                    elif pos < 0.9:
                        stage = "Falling Action"
                    else:
                        stage = "Denouement"
                    val = sample_arc_at_pos(pos)
                    sentence_classifications.append({"index": i, "stage": stage, "value": float(val)})

            # Aggregate per-stage average values
            from collections import defaultdict
            sums = defaultdict(float)
            counts = defaultdict(int)
            for c in sentence_classifications:
                sums[c["stage"]] += c["value"]
                counts[c["stage"]] += 1

            stages_order = ["Exposition", "Rising Action", "Climax", "Falling Action", "Denouement"]
            stage_values = []
            for stage in stages_order:
                if counts.get(stage, 0) > 0:
                    stage_values.append({"stage": stage, "value": sums[stage] / counts[stage]})
                else:
                    stage_values.append({"stage": stage, "value": 0.0})

    return schemas.StoryArcResponse(
        arc=result["arc"],
        beats=result.get("beats", []),
        sentence_classifications=sentence_classifications,
        stage_values=stage_values,
    )