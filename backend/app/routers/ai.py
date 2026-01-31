"""AI-powered endpoints for character suggestion and text generation."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import re

from app.database import get_db
from app import models, schemas
from app.services import ai_client
from app.services.ai_client import (
    generate_spider_intent,
    generate_beats_for_arc,
    reformulate_sentence_for_tension,
    analyze_character_sentiment,
    analyze_character_pattern,
    discover_characters_in_text,
    clear_character_emoji_mappings,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _sentence_mentions_character(sentence_text: str, character_name: str, aliases: list) -> bool:
    """True if the sentence contains the character name or any alias (word boundary)."""
    text_lower = sentence_text.lower()
    terms = [character_name.lower()] + [a.lower() for a in (aliases or []) if a]
    for term in terms:
        if not term.strip():
            continue
        if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
            return True
    return False


# Negative descriptors that clearly frame the character (not "merely mentioned")
_NEGATIVE_FRAMING_WORDS = {
    "fearsome", "fierce", "cruel", "evil", "menacing", "savage", "monstrous",
    "terrible", "dreadful", "wicked", "vile", "cowardly", "shamefully",
    "ferocious", "bloodthirsty", "ruthless", "malicious", "treacherous",
}


def _is_mere_mention(sentence_text: str, character_name: str, aliases: list) -> bool:
    """
    True if the character is only mentioned (e.g. as opponent in a fight)
    with no adjectives framing them positively or negatively.
    E.g. "The hero fought bravely against the dragon in an epic battle." → dragon: mere mention → neutral.
    """
    text_lower = sentence_text.lower().strip()
    terms = [character_name.lower()] + [a.lower() for a in (aliases or []) if a and a.strip()]
    if not terms:
        return False
    # Pattern: (fought|battled|faced) [optional words] against (the)? CHARACTER; or "against (the)? CHARACTER in ... battle"
    char_pattern = "|".join(re.escape(t) for t in terms)
    mere_mention_pattern = re.compile(
        r"\b(?:fought|battled|faced|facing)\s+(?:\w+\s+)*against\s+(?:the\s+)?(?:"
        + char_pattern
        + r")\b|\bagainst\s+(?:the\s+)?(?:"
        + char_pattern
        + r")\s+in\s+(?:\w+\s+)*battle",
        re.IGNORECASE,
    )
    if not mere_mention_pattern.search(text_lower):
        return False
    # If sentence contains negative framing words near the character, not "mere mention"
    for word in _NEGATIVE_FRAMING_WORDS:
        if word in text_lower:
            return False
    return True


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
    
    # If characters are defined in request, use character-based matching logic
    character_refs = []
    character_word_mappings = {}
    text_lower = request.text.lower()
    
    if request.characters and len(request.characters) > 0:
        # CHARACTER-BASED GENERATION: Match predefined characters in text
        
        for character in request.characters:
            # Check if character name appears as whole word in text
            name_lower = character['name'].lower()
            if re.search(r'\b' + re.escape(name_lower) + r'\b', text_lower):
                character_refs.append(character['id'])
                character_word_mappings[name_lower] = character['emoji']
                continue
            
            # Check aliases
            for alias in character.get('aliases', []):
                alias_lower = alias.lower()
                if re.search(r'\b' + re.escape(alias_lower) + r'\b', text_lower):
                    character_refs.append(character['id'])
                    character_word_mappings[alias_lower] = character['emoji']
                    break
    else:
        # FREE GENERATION: Check if any existing characters are mentioned in this sentence
        for char in all_characters:
            # Get all words that belong to this character
            character_words = set()
            character_words.add(char.name.lower())
            
            # Add aliases
            if char.aliases:
                try:
                    aliases = json.loads(char.aliases)
                    character_words.update([alias.lower() for alias in aliases])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Add word phrases  
            if char.word_phrases:
                try:
                    word_phrases = json.loads(char.word_phrases)
                    character_words.update([phrase.lower() for phrase in word_phrases])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Check if any character word appears in the text
            found_character_match = False
            for word in character_words:
                if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                    # Only assign word to emoji if not already assigned to avoid duplicates
                    if word not in character_word_mappings:
                        character_word_mappings[word] = char.emoji
                        found_character_match = True
            
            # Add character reference if any word matched
            if found_character_match and char.id not in character_refs:
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
    
    # CLEANUP: Remove any character words from emoji mappings to prevent contamination
    if emoji_word_mappings:
        # Get all character words to filter out
        all_character_words = set()
        for char in all_characters:
            all_character_words.add(char.name.lower())
            if char.aliases:
                try:
                    aliases = json.loads(char.aliases)
                    all_character_words.update([alias.lower() for alias in aliases])
                except (json.JSONDecodeError, TypeError):
                    pass
            if char.word_phrases:
                try:
                    word_phrases = json.loads(char.word_phrases)
                    all_character_words.update([phrase.lower() for phrase in word_phrases])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Clean emoji mappings AND apply separation logic
        cleaned_mappings = {}
        for emoji, phrases in emoji_word_mappings.items():
            if isinstance(phrases, list):
                # Remove character words
                remaining_phrases = [
                    phrase for phrase in phrases 
                    if phrase.lower() not in all_character_words
                ]
                
                # Apply separation logic: split conflicting entities
                if remaining_phrases:
                    separated_phrases = _separate_conflicting_entities(remaining_phrases)
                    if separated_phrases:  # Only keep if still has phrases after separation
                        cleaned_mappings[emoji] = separated_phrases
        
        sentence.emoji_mappings = json.dumps(cleaned_mappings) if cleaned_mappings else None
    else:
        sentence.emoji_mappings = None
        
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
    DEPRECATED: Use /generate-emojis instead.
    
    This endpoint now just delegates to generate_emojis_freely for backward compatibility.
    The main generate-emojis endpoint handles both character-based and free generation.
    """
    return await generate_emojis_freely(request, db)


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
    
def _separate_conflicting_entities(phrases: list[str]) -> list[str]:
    """
    Separate phrases that represent different entities to prevent contamination.
    
    For example, if phrases contain both 'dragon' and 'hero', they likely represent
    different entities and shouldn't be grouped under the same emoji.
    
    Args:
        phrases: List of word phrases assigned to an emoji
        
    Returns:
        Filtered list with conflicting entities removed
    """
    if not phrases or len(phrases) <= 1:
        return phrases
    
    # Common character/entity role words that shouldn't be mixed
    character_roles = {
        'hero', 'heroine', 'protagonist', 'main character',
        'villain', 'antagonist', 'evil', 'dark lord',
        'dragon', 'monster', 'beast', 'creature',
        'king', 'queen', 'prince', 'princess', 'royal',
        'wizard', 'witch', 'mage', 'sorcerer',
        'knight', 'warrior', 'fighter', 'soldier',
        'guard', 'captain', 'general', 'commander'
    }
    
    # Find character roles in the phrases
    found_roles = []
    role_phrases = {}  # role -> [phrases containing that role]
    
    for phrase in phrases:
        phrase_lower = phrase.lower().strip()
        for role in character_roles:
            if role in phrase_lower:
                if role not in role_phrases:
                    role_phrases[role] = []
                    found_roles.append(role)
                role_phrases[role].append(phrase)
                break  # Only assign to first matching role
    
    # If multiple character roles found, keep only the most represented one
    if len(found_roles) > 1:
        # Count phrases for each role
        role_counts = {role: len(role_phrases[role]) for role in found_roles}
        # Keep the role with most phrases
        dominant_role = max(role_counts.keys(), key=lambda r: role_counts[r])
        
        # Filter out phrases from other roles
        filtered_phrases = []
        for phrase in phrases:
            phrase_lower = phrase.lower().strip()
            # Keep phrase if it doesn't contain conflicting roles, or contains dominant role
            contains_dominant = dominant_role in phrase_lower
            contains_other_role = any(role != dominant_role and role in phrase_lower for role in found_roles)
            
            if contains_dominant or not contains_other_role:
                filtered_phrases.append(phrase)
        
        return filtered_phrases
    
    # No conflicts found, return all phrases
    return phrases


# Helper function for AI router to access the separation logic
def separate_conflicting_entities(phrases: list[str]) -> list[str]:
    """Public interface to the entity separation logic."""
    return _separate_conflicting_entities(phrases)



@router.post("/clear-character-mappings")
async def clear_character_mappings():
    """
    🎭 Clear character-emoji consistency cache.
    
    Call this when switching to a new document or starting fresh.
    This allows characters in different stories to get different emojis.
    """
    clear_character_emoji_mappings()
    return {"status": "cleared", "message": "Character-emoji mappings cleared"}


@router.post("/clear-cache")
async def clear_ai_cache(character_sentiment: bool = True, character_emoji: bool = True):
    """
    Clear in-memory AI caches.
    
    - character_sentiment: clear character portrayal/sentiment cache (so re-analyzing uses fresh LLM results).
    - character_emoji: clear character-emoji mapping cache.
    Call with no query params to clear both.
    """
    cleared = []
    if character_sentiment:
        _character_sentiment_cache.clear()
        cleared.append("character_sentiment")
    if character_emoji:
        clear_character_emoji_mappings()
        cleared.append("character_emoji")
    return {"status": "cleared", "caches": cleared}


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

def split_into_sentences(text: str) -> list[str]:
    text = text.replace("\n", " ").strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s for s in sentences if s]

def assign_beat_positions_with_ranges(beats, total_sentences):
    STAGE_RANGES = {
        "Exposition": (0.0, 0.19),
        "Rising Action": (0.2, 0.39),
        "Climax": (0.4, 0.59),
        "Falling Action": (0.6, 0.79),
        "Denouement": (0.8, 1.0),
    }

    offset_step = 0.03  # for multiple fallbacks in same stage

    for b in beats:
        start, end = STAGE_RANGES[b["name"]]
        idx = b.get("sentence_index")

        if idx is not None and total_sentences > 1:
            # realtive Position in the stage range
            pos_in_text = idx / (total_sentences - 1)
            b["position"] = start + (end - start) * pos_in_text
            b["has_sentence"] = True
        else:
            # no sentence assigned --> place in middle of stage range
            b["position"] = start + (end - start) / 2
            b["has_sentence"] = False

    # Adjust positions for multiple fallbacks in same stage
    stage_groups = {}
    for b in beats:
        if not b["has_sentence"]:
            stage_groups.setdefault(b["name"], []).append(b)

    for group in stage_groups.values():
        n = len(group)
        if n == 1:
            continue
        total_span = offset_step * (n - 1)
        start_offset = -total_span / 2
        for i, b in enumerate(group):
            b["position"] += start_offset + i * offset_step
            b["position"] = max(0.0, min(1.0, b["position"]))



def build_arc_from_beats(beats, granularity=20):
    """
    Builds the story arc curve using beat positions and values.
    - Sentence beats are exactly at their positions
    - Fallback beats with value=0.0
    """
    arc = []
    if not beats:
        return [0.0] * granularity

    # Sort by position
    sorted_beats = sorted(beats, key=lambda b: b["position"])

    for i in range(granularity):
        pos = i / max(1, granularity - 1)

        # Find left and right beats for interpolation
        for j in range(len(sorted_beats) - 1):
            left = sorted_beats[j]
            right = sorted_beats[j + 1]
            if left["position"] <= pos <= right["position"]:
                span = right["position"] - left["position"]
                t = (pos - left["position"]) / span if span > 0 else 0
                value = (1 - t) * left["value"] + t * right["value"]
                arc.append(value)
                break
        else:
            # pos is before first beat or after last beat
            if pos < sorted_beats[0]["position"]:
                arc.append(sorted_beats[0]["value"])
            else:
                arc.append(sorted_beats[-1]["value"])

    return arc

@router.post("/story-arc", response_model=schemas.StoryArcResponse)
async def compute_story_arc(request: schemas.StoryArcRequest, db: Session = Depends(get_db)):

    # 1. Load the text from the document
    text = request.text
    if request.document_id and not text:
        document = db.query(models.Document).filter(models.Document.id == request.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        text = (document.title or "") + "\n\n" + (document.body or "")

    if not text:
        raise HTTPException(status_code=400, detail="No text provided for story arc analysis")

    granularity = request.granularity or 20

    # 2. Generate AI-Story Arc & Beats
    result = await generate_beats_for_arc(text=text)
    beats = result.get("beats", [])

    all_sentences = split_into_sentences(text)
    total_sentences = len(all_sentences)
    print("All Sentences:", total_sentences)

    # 3. Assign Beats to Sentences and Positions on the story arc and generate the Arc
    # 3.1 Assign Beats to Sentences and Positions
    assign_beat_positions_with_ranges(beats, total_sentences)

    # 3.2 Build Arc using the final positions
    arc_vals = build_arc_from_beats(beats, granularity)

    # 4. Stage-Values
    stage_values = [{"stage": b["name"], "value": float(b.get("value", 0.0))} for b in beats]
    print("Stage Values:", stage_values)
    print("=== BEATS (source of truth) ===")
    for b in beats:
        print(
            f"{b['name']:15} "
            f"x={b['position']:.3f} "
            f"y={b['value']:.3f} "
            f"{b['note']:15} "
            f"sentence={b.get('sentence_index')}"
        )

    return schemas.StoryArcResponse(
        arc=arc_vals,
        beats=beats,
        stage_values=stage_values
    )


@router.post("/reformulate-sentence-tension", response_model=schemas.ReformulateSentenceResponse)
async def reformulate_sentence_tension(
    request: schemas.ReformulateSentenceRequest,
    db: Session = Depends(get_db)
):
    """
    Reformulate a sentence to match a specific tension value (0.0 to 1.0).
    The tension value represents narrative intensity on the story arc.
    """
    # Verify sentence exists
    sentence = db.query(models.Sentence).filter(
        models.Sentence.id == request.sentence_id
    ).first()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Verify document exists
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Reformulate sentence using AI service
    try:
        reformulated_text = await reformulate_sentence_for_tension(
            text=request.text,
            tension_value=request.tension_value
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reformulate sentence: {str(e)}"
        )
    
    return schemas.ReformulateSentenceResponse(
        sentence_id=request.sentence_id,
        reformulated_text=reformulated_text
    )


@router.delete("/clear-emojis/{document_id}")
async def clear_document_emojis(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Clear all emoji mappings for a specific document and reset characters."""
    try:
        # Verify document exists
        document = db.query(models.Document).filter(
            models.Document.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Clear emoji_mappings AND emojis for all sentences in the document
        db.query(models.Sentence).filter(
            models.Sentence.document_id == document_id
        ).update({
            "emoji_mappings": "{}",
            "emojis": "[]"
        })
        
        # Clear word_phrases for all characters (but keep the characters)
        db.query(models.Character).filter(
            models.Character.document_id == document_id
        ).update({"word_phrases": "[]"})
        
        db.commit()
        
        return {"message": f"Cleared emoji mappings and character word phrases for document {document_id}"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear emoji mappings: {str(e)}"
        )


# In-memory cache for character sentiment: same (document, chapter) returns same result until server restart.
_character_sentiment_cache: dict = {}
_CACHE_KEY_MAX_SIZE = 200  # Limit cache size to avoid unbounded growth


def _character_sentiment_cache_key(document_id: str, chapter_id: Optional[str], character_ids: Optional[list]) -> tuple:
    cids = tuple(sorted(character_ids)) if character_ids else "all"
    return (document_id, chapter_id if chapter_id else "all", cids)


async def _analyze_character_sentiment_for_scope(
    db: Session,
    document_id: str,
    chapter_id: Optional[str],
    character_ids: Optional[list[str]],
) -> schemas.CharacterSentimentAnalysisResponse:
    """
    Run character sentiment analysis for a single scope (one chapter or full doc).
    Uses and updates the per-scope cache.
    """
    import asyncio

    cache_key = _character_sentiment_cache_key(document_id, chapter_id, character_ids)
    if cache_key in _character_sentiment_cache:
        cached = _character_sentiment_cache[cache_key]
        return schemas.CharacterSentimentAnalysisResponse.model_validate(cached)

    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    sentence_query = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    )
    if chapter_id:
        sentence_query = sentence_query.filter(models.Sentence.chapter_id == chapter_id)
    sentences = sentence_query.order_by(models.Sentence.index).all()
    full_text = " ".join([s.text for s in sentences])

    if not full_text.strip():
        return schemas.CharacterSentimentAnalysisResponse(characters=[])

    total_sentences_in_scope = len(sentences)

    if character_ids:
        characters = db.query(models.Character).filter(
            models.Character.document_id == document_id,
            models.Character.id.in_(character_ids),
        ).all()
    else:
        characters = db.query(models.Character).filter(
            models.Character.document_id == document_id
        ).all()

    if not characters:
        print("No characters defined, discovering characters using LLM...")
        discovered_chars = await discover_characters_in_text(full_text)
        characters_to_analyze = [
            {
                "id": f"discovered_{char_data.get('name', '').lower().replace(' ', '_')}",
                "name": char_data.get("name", "Unknown"),
                "emoji": "👤",
                "aliases": char_data.get("aliases", []),
            }
            for char_data in discovered_chars
        ]
    else:
        characters_to_analyze = [
            {
                "id": char.id,
                "name": char.name,
                "emoji": char.emoji,
                "aliases": json.loads(char.aliases) if char.aliases else [],
            }
            for char in characters
        ]

    if not characters_to_analyze:
        return schemas.CharacterSentimentAnalysisResponse(characters=[])

    async def get_pattern(c):
        return await analyze_character_pattern(full_text, c["name"], c.get("aliases", []))
    character_patterns = await asyncio.gather(*[get_pattern(c) for c in characters_to_analyze])

    async def analyze_single_character(char_data, character_pattern: Optional[str] = None):
        try:
            char_name = char_data["name"]
            aliases = char_data.get("aliases", [])
            mentioning_list = [
                (i, sentences[i].text)
                for i in range(len(sentences))
                if _sentence_mentions_character(sentences[i].text, char_name, aliases)
            ]
            if not mentioning_list:
                return schemas.CharacterSentimentResponse(
                    character_id=char_data["id"],
                    character_name=char_name,
                    emoji=char_data.get("emoji", "👤"),
                    mention_count=0,
                    positive_percentage=0,
                    neutral_percentage=0,
                    negative_percentage=0,
                    mentions=[],
                    trend_points=[],
                )
            SEGMENT_SEP = " --- SEGMENT --- "
            segments = []
            for (scope_index, sentence_text) in mentioning_list:
                start = max(0, scope_index - 2)
                end = min(len(sentences), scope_index + 3)
                context_sentences = [sentences[j].text for j in range(start, end)]
                segments.append(" ".join(context_sentences))
            text_for_llm = SEGMENT_SEP.join(segments)
            sentiment_result = await analyze_character_sentiment(
                text=text_for_llm,
                character_name=char_name,
                character_aliases=aliases,
                character_pattern=character_pattern,
            )
            mentions = []
            ai_mentions = sentiment_result.get("mentions", [])
            for k, (scope_index, sentence_text) in enumerate(mentioning_list):
                mention_data = ai_mentions[k] if k < len(ai_mentions) else {}
                sentiment = mention_data.get("sentiment", "neutral")
                if _is_mere_mention(sentence_text, char_name, aliases):
                    sentiment = "neutral"
                position = (
                    scope_index / (total_sentences_in_scope - 1)
                    if total_sentences_in_scope > 1
                    else 0.0
                )
                mentions.append(
                    schemas.CharacterSentimentMention(
                        sentence_index=scope_index,
                        sentence_text=sentence_text,
                        sentiment=sentiment,
                        position=position,
                    )
                )
            total = len(mentions)
            positive_percentage = int((sum(1 for m in mentions if m.sentiment == "positive") / total) * 100)
            neutral_percentage = int((sum(1 for m in mentions if m.sentiment == "neutral") / total) * 100)
            negative_percentage = int((sum(1 for m in mentions if m.sentiment == "negative") / total) * 100)
            trend_points = [
                0.7 if m.sentiment == "positive" else (0.3 if m.sentiment == "negative" else 0.5)
                for m in mentions
            ]
            return schemas.CharacterSentimentResponse(
                character_id=char_data["id"],
                character_name=char_name,
                emoji=char_data.get("emoji", "👤"),
                mention_count=len(mentions),
                positive_percentage=positive_percentage,
                neutral_percentage=neutral_percentage,
                negative_percentage=negative_percentage,
                mentions=mentions,
                trend_points=trend_points,
            )
        except Exception as e:
            print(f"❌ Error analyzing character {char_data.get('name', 'unknown')}: {e}")
            return schemas.CharacterSentimentResponse(
                character_id=char_data["id"],
                character_name=char_data["name"],
                emoji=char_data.get("emoji", "👤"),
                mention_count=0,
                positive_percentage=0,
                neutral_percentage=0,
                negative_percentage=0,
                mentions=[],
                trend_points=[],
            )

    character_sentiments = await asyncio.gather(*[
        analyze_single_character(char_data, character_patterns[i] if i < len(character_patterns) else None)
        for i, char_data in enumerate(characters_to_analyze)
    ])
    response = schemas.CharacterSentimentAnalysisResponse(characters=character_sentiments)
    _character_sentiment_cache[cache_key] = response.model_dump()
    if len(_character_sentiment_cache) > _CACHE_KEY_MAX_SIZE:
        keys_to_drop = list(_character_sentiment_cache.keys())[:_CACHE_KEY_MAX_SIZE // 2]
        for k in keys_to_drop:
            _character_sentiment_cache.pop(k, None)
    return response


@router.post("/analyze-character-sentiment", response_model=schemas.CharacterSentimentAnalysisResponse)
async def analyze_character_sentiment_endpoint(
    request: schemas.CharacterSentimentAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze sentiment for characters in the document.
    If chapter_id is null (Entire Story / Overview), aggregates per-chapter results so the overview
    matches what you see in each single section. If chapter_id is set, analyzes that chapter only.
    """
    import asyncio

    document_id = request.document_id
    chapter_id = request.chapter_id
    character_ids = request.character_ids

    # Single scope: use cached or run analysis for that chapter (or full doc if no chapters)
    if chapter_id is not None:
        return await _analyze_character_sentiment_for_scope(db, document_id, chapter_id, character_ids)

    # Entire Story (Overview): aggregate per-chapter results so overview matches single-section view
    cache_key = _character_sentiment_cache_key(document_id, None, character_ids)
    if cache_key in _character_sentiment_cache:
        cached = _character_sentiment_cache[cache_key]
        return schemas.CharacterSentimentAnalysisResponse.model_validate(cached)

    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Ordered chapters (by index)
    chapters = list(document.chapters) if hasattr(document, "chapters") and document.chapters else []
    if not chapters:
        # No chapters: run single analysis on full document
        return await _analyze_character_sentiment_for_scope(db, document_id, None, character_ids)

    all_sentences = (
        db.query(models.Sentence)
        .filter(models.Sentence.document_id == document_id)
        .order_by(models.Sentence.index)
        .all()
    )
    total_sentences = len(all_sentences)
    # For each chapter, list of global sentence indices (so we can map chapter-local index -> global)
    chapter_global_indices: dict[str, list[int]] = {}
    for ch in chapters:
        indices = sorted([s.index for s in all_sentences if s.chapter_id == ch.id])
        chapter_global_indices[ch.id] = indices

    # Run analysis per chapter (uses cache per chapter)
    chapter_responses = await asyncio.gather(*[
        _analyze_character_sentiment_for_scope(db, document_id, ch.id, character_ids)
        for ch in chapters
    ])

    # Merge: for each character, concatenate mentions from all chapters with global sentence_index and position
    template = chapter_responses[0]
    merged_characters = []
    for char_resp in template.characters:
        merged_mentions = []
        for i, ch in enumerate(chapters):
            ch_resp = chapter_responses[i] if i < len(chapter_responses) else None
            if not ch_resp:
                continue
            char_in_ch = next((c for c in ch_resp.characters if c.character_id == char_resp.character_id), None)
            if not char_in_ch or not char_in_ch.mentions:
                continue
            global_indices = chapter_global_indices.get(ch.id, [])
            for m in char_in_ch.mentions:
                if m.sentence_index < len(global_indices):
                    global_index = global_indices[m.sentence_index]
                    position = global_index / (total_sentences - 1) if total_sentences > 1 else 0.0
                    merged_mentions.append(
                        schemas.CharacterSentimentMention(
                            sentence_index=global_index,
                            sentence_text=m.sentence_text,
                            sentiment=m.sentiment,
                            position=position,
                        )
                    )
        merged_mentions.sort(key=lambda x: x.sentence_index)
        total = len(merged_mentions)
        if total == 0:
            merged_characters.append(
                schemas.CharacterSentimentResponse(
                    character_id=char_resp.character_id,
                    character_name=char_resp.character_name,
                    emoji=char_resp.emoji,
                    mention_count=0,
                    positive_percentage=0,
                    neutral_percentage=0,
                    negative_percentage=0,
                    mentions=[],
                    trend_points=[],
                )
            )
            continue
        positive_pct = int((sum(1 for m in merged_mentions if m.sentiment == "positive") / total) * 100)
        neutral_pct = int((sum(1 for m in merged_mentions if m.sentiment == "neutral") / total) * 100)
        negative_pct = int((sum(1 for m in merged_mentions if m.sentiment == "negative") / total) * 100)
        trend_points = [
            0.7 if m.sentiment == "positive" else (0.3 if m.sentiment == "negative" else 0.5)
            for m in merged_mentions
        ]
        merged_characters.append(
            schemas.CharacterSentimentResponse(
                character_id=char_resp.character_id,
                character_name=char_resp.character_name,
                emoji=char_resp.emoji,
                mention_count=total,
                positive_percentage=positive_pct,
                neutral_percentage=neutral_pct,
                negative_percentage=negative_pct,
                mentions=merged_mentions,
                trend_points=trend_points,
            )
        )
    response = schemas.CharacterSentimentAnalysisResponse(characters=merged_characters)
    _character_sentiment_cache[cache_key] = response.model_dump()
    if len(_character_sentiment_cache) > _CACHE_KEY_MAX_SIZE:
        keys_to_drop = list(_character_sentiment_cache.keys())[:_CACHE_KEY_MAX_SIZE // 2]
        for k in keys_to_drop:
            _character_sentiment_cache.pop(k, None)
    return response
