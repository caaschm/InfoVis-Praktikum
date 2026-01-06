"""AI-powered endpoints for character suggestion and text generation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import re

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
    
    # If characters are defined, use character-based suggestion
    if request.characters and len(request.characters) > 0:
        return await suggest_characters_for_text(request, db)
    
    # Otherwise, generate emojis freely based on semantic content
    # TODO: Replace with real AI emoji generation
    
    # Simple placeholder: Extract meaningful words and assign emojis
    text_lower = request.text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Filter out common function words
    meaningful_words = [w for w in words if w not in IGNORE_WORDS]
    
    # Simple emoji mapping (placeholder for AI)
    emoji_map = {
        'princess': '👸',
        'prince': '🤴',
        'king': '🤴',
        'queen': '👸',
        'dragon': '🐉',
        'knight': '⚔️',
        'castle': '🏰',
        'forest': '🌲',
        'magic': '✨',
        'sword': '⚔️',
        'crown': '👑',
        'horse': '🐴',
        'love': '❤️',
        'happy': '😊',
        'sad': '😢',
        'angry': '😠',
        'surprised': '😲'
    }
    
    # Generate emoji "characters" for meaningful words
    suggested_emojis = []
    for word in meaningful_words[:5]:  # Limit to 5 emojis
        emoji = emoji_map.get(word, '⭐')  # Default to star
        if emoji not in suggested_emojis:
            suggested_emojis.append(emoji)
    
    # Save emojis to sentence
    sentence.emojis = json.dumps(suggested_emojis)
    db.commit()
    
    # Return raw emojis (no character refs yet)
    return schemas.CharacterSuggestionResponse(
        sentence_id=request.sentence_id,
        emojis=suggested_emojis,
        character_refs=[]
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
    
    TODO: Implement AI-powered detection.
    """
    # Verify sentence exists
    sentence = db.query(models.Sentence).filter(
        models.Sentence.id == request.sentence_id
    ).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # If no characters defined, generate freely
    if not request.characters or len(request.characters) == 0:
        # Free generation mode
        text_lower = request.text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Filter out common function words
        meaningful_words = [w for w in words if w not in IGNORE_WORDS]
        
        # Simple emoji mapping (placeholder for AI)
        emoji_map = {
            'princess': '👸',
            'prince': '🤴',
            'king': '🤴',
            'queen': '👸',
            'dragon': '🐉',
            'knight': '⚔️',
            'castle': '🏰',
            'forest': '🌲',
            'magic': '✨',
            'sword': '⚔️',
            'crown': '👑',
            'horse': '🐴',
            'love': '❤️',
            'happy': '😊',
            'sad': '😢',
            'angry': '😠',
            'surprised': '😲'
        }
        
        # Generate emojis for meaningful words
        suggested_emojis = []
        for word in meaningful_words[:5]:  # Limit to 5 emojis
            emoji = emoji_map.get(word, '⭐')  # Default to star
            if emoji not in suggested_emojis:
                suggested_emojis.append(emoji)
        
        # Save emojis to sentence
        sentence.emojis = json.dumps(suggested_emojis)
        sentence.character_refs = json.dumps([])
        db.commit()
        
        return schemas.CharacterSuggestionResponse(
            sentence_id=request.sentence_id,
            emojis=suggested_emojis,
            character_refs=[]
        )
    
    # Character-based generation mode (HYBRID: characters + free emojis)
    text_lower = request.text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    meaningful_words = [w for w in words if w not in IGNORE_WORDS]
    
    suggested_refs = []
    suggested_emojis = []
    matched_words = set()  # Track words already covered by characters
    
    # First pass: Match characters
    for character in request.characters:
        # Check if character name or any alias appears in text
        name_lower = character['name'].lower()
        if name_lower in text_lower:
            suggested_refs.append(character['id'])
            suggested_emojis.append(character['emoji'])
            matched_words.add(name_lower)
            continue
        
        for alias in character.get('aliases', []):
            alias_lower = alias.lower()
            if alias_lower in text_lower:
                suggested_refs.append(character['id'])
                suggested_emojis.append(character['emoji'])
                matched_words.add(alias_lower)
                break
    
    # Second pass: Generate free emojis for unmatched words
    emoji_map = {
        'journey': '🗺️',
        'embarks': '🚶',
        'adventure': '⚔️',
        'quest': '🎯',
        'princess': '👸',
        'prince': '🤴',
        'king': '🤴',
        'queen': '👸',
        'dragon': '🐉',
        'knight': '⚔️',
        'castle': '🏰',
        'forest': '🌲',
        'magic': '✨',
        'sword': '⚔️',
        'crown': '👑',
        'horse': '🐴',
        'love': '❤️',
        'happy': '😊',
        'sad': '😢',
        'angry': '😠',
        'surprised': '😲',
        'tree': '🌳',
        'mountain': '⛰️',
        'river': '🌊',
        'sun': '☀️',
        'moon': '🌙',
        'star': '⭐',
        'fire': '🔥',
        'water': '💧',
        'wind': '💨',
        'earth': '🌍',
        'village': '🏘️',
        'town': '🏙️',
        'city': '🏙️',
        'home': '🏠',
        'house': '🏠',
        'door': '🚪',
        'window': '🪟',
        'treasure': '💎',
        'gold': '🪙',
        'silver': '🥈',
        'weapon': '⚔️',
        'shield': '🛡️',
        'armor': '🛡️',
        'battle': '⚔️',
        'fight': '🥊',
        'war': '⚔️',
        'peace': '☮️',
        'friend': '👫',
        'enemy': '👿',
        'hero': '🦸',
        'villain': '🦹',
        'witch': '🧙',
        'wizard': '🧙',
        'monster': '👹',
        'beast': '🐻',
        'bird': '🐦',
        'fish': '🐟',
        'dog': '🐕',
        'cat': '🐈',
        'food': '🍔',
        'drink': '🥤',
        'book': '📖',
        'letter': '✉️',
        'message': '💌',
        'secret': '🤫',
        'mystery': '🔍',
        'danger': '⚠️',
        'warning': '⚠️',
        'death': '💀',
        'life': '🌱',
        'birth': '👶',
        'child': '👶',
        'old': '👴',
        'young': '👦',
        'beautiful': '✨',
        'ugly': '👹',
        'strong': '💪',
        'weak': '🤕',
        'brave': '🦁',
        'afraid': '😨',
        'dark': '🌑',
        'light': '💡',
        'night': '🌃',
        'day': '🌅',
        'morning': '🌄',
        'evening': '🌆'
    }
    
    for word in meaningful_words:
        if word not in matched_words and word in emoji_map:
            emoji = emoji_map[word]
            if emoji not in suggested_emojis:
                suggested_emojis.append(emoji)
    
    # Fallback: If no emojis generated and there are meaningful words, add a generic emoji
    if len(suggested_emojis) == 0 and len(meaningful_words) > 0:
        suggested_emojis.append('⭐')  # Generic placeholder
    
    # PRESERVE EXISTING: Merge with existing emojis (non-destructive)
    existing_emojis = json.loads(sentence.emojis) if sentence.emojis else []
    existing_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
    
    # Merge: Add new emojis to existing ones (no duplicates)
    for emoji in existing_emojis:
        if emoji not in suggested_emojis:
            suggested_emojis.insert(0, emoji)  # Preserve order
    
    # Merge: Add new character refs to existing ones
    for ref in existing_refs:
        if ref not in suggested_refs:
            suggested_refs.insert(0, ref)
    
    # Save merged results
    sentence.emojis = json.dumps(suggested_emojis)
    sentence.character_refs = json.dumps(suggested_refs)
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
