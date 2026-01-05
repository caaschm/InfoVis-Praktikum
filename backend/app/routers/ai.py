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
    Also classify sentences to stages and aggregate stage tension values.
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

    granularity = request.granularity or 20
    stages_order = ["Exposition", "Rising Action", "Climax", "Falling Action", "Denouement"]

    # 1️⃣ Generate story arc & beats via AI
    try:
        result = await generate_story_arc(text=text, granularity=granularity)
        arc_raw = result.get("arc", [0.5]*granularity)
        beats = result.get("beats", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute story arc: {e}")

    # 2️⃣ Load sentences if document_id provided
    sentences = []
    if request.document_id:
        sentences = db.query(models.Sentence).filter(
            models.Sentence.document_id == request.document_id
        ).order_by(models.Sentence.index).all()

    N = len(sentences)

    # 3️⃣ Map beats to nearest sentences for clickable notes
    if sentences and beats:
        for b in beats:
            pos = float(b.get("position", 0))
            si = int(round(pos * (N-1))) if N > 0 else 0
            si = max(0, min(N-1, si))
            b["sentence_index"] = si
            b["sentence_id"] = sentences[si].id if N > 0 else None
            b["note"] = sentences[si].text if N > 0 else ""

        # Ensure positions are monotonically increasing
        last_pos = 0.0
        for b in beats:
            b["position"] = max(last_pos, b["position"])
            last_pos = b["position"]

    # 4️⃣ Sentence classification
    sentence_classifications = []
    if sentences:
        try:
            classifications = await generate_sentence_stage_mapping(text, [s.text for s in sentences])
        except Exception as e:
            print("❌ Error classifying sentences:", e)
            classifications = []

        # Build index -> classification map
        cls_map = {c["index"]: c for c in classifications if "index" in c}

        DEFAULT_STAGE_VALUES = {
            "Exposition": 0.15,
            "Rising Action": 0.35,
            "Climax": 0.9,
            "Falling Action": 0.4,
            "Denouement": 0.2
        }

        SIGNIFICANT_THRESHOLD = 0.01


        sentence_classifications = []

        for i in range(N):
            if i in cls_map:
                item = cls_map[i]
                stage = item["stage"]
                val = item.get("value")
                if val is None:
                    val = DEFAULT_STAGE_VALUES[stage]
            else:
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
                val = DEFAULT_STAGE_VALUES[stage]

        sentence_classifications.append({
            "index": i,
            "stage": stage,
            "value": float(val),
            "significant": float(val) >= SIGNIFICANT_THRESHOLD
        })
    # 5️⃣ Aggregate per-stage tension values
    from collections import defaultdict
    sums, counts = defaultdict(float), defaultdict(int)
    for c in sentence_classifications:
        sums[c["stage"]] += c["value"]
        counts[c["stage"]] += 1

    stage_values = []
    for stage in stages_order:
        if counts.get(stage, 0) > 0:
            stage_values.append({"stage": stage, "value": sums[stage]/counts[stage]})
        else:
            stage_values.append({"stage": stage, "value": 0.0})

    # 6️⃣ Ensure arc is consistent: flat if all stage values = 0
    stage_curve = [
        v["value"] for v in stage_values
    ]

    # simple linear interpolation über Stages → Arc
    arc_vals = []
    for i in range(granularity):
        pos = i / max(1, granularity - 1)
        f = pos * (len(stage_curve) - 1)
        lo, hi = int(f), min(int(f) + 1, len(stage_curve) - 1)
        t = f - lo
        arc_vals.append((1 - t) * stage_curve[lo] + t * stage_curve[hi])


    return schemas.StoryArcResponse(
        arc=arc_vals,
        beats=beats,
        sentence_classifications=sentence_classifications,
        stage_values=stage_values
    )