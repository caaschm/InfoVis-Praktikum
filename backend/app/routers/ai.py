"""AI-powered endpoints for character suggestion and text generation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import re
from pydantic import BaseModel

from app.database import get_db
from app import models, schemas
from app.services import ai_client
from app.services.ai_client import generate_spider_intent, generate_beats_for_arc, reformulate_sentence_for_tension, analyze_character_sentiment, discover_characters_in_text

router = APIRouter(prefix="/api/ai", tags=["ai"])

class ModelUpdate(BaseModel):
    index: int

@router.get("/get-models")
async def get_models():
    return {
        "models": ai_client.AI_MODELS,
        "current_index": ai_client.current_index
    }

@router.post("/set-model")
async def set_model(data: ModelUpdate):
    if 0 <= data.index < len(ai_client.AI_MODELS):
        ai_client.current_index = data.index
        ai_client.MODEL_NAME = ai_client.AI_MODELS[data.index]
        return {"status": "success", "current_model": ai_client.MODEL_NAME}
    raise HTTPException(status_code=400, detail="Invalid index")

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


@router.post("/analyze-character-sentiment", response_model=schemas.CharacterSentimentAnalysisResponse)
async def analyze_character_sentiment_endpoint(
    request: schemas.CharacterSentimentAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment for characters in the document.
    If character_ids is provided, analyzes only those characters.
    Otherwise, analyzes all characters in the document.
    If no characters are defined, uses LLM to discover characters from the text.
    """
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == request.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get sentences for the document, optionally filtered by chapter
    sentence_query = db.query(models.Sentence).filter(
        models.Sentence.document_id == request.document_id
    )
    
    # Filter by chapter if specified
    if request.chapter_id:
        sentence_query = sentence_query.filter(
            models.Sentence.chapter_id == request.chapter_id
        )
    
    sentences = sentence_query.order_by(models.Sentence.index).all()
    
    # Build full text from sentences
    full_text = " ".join([s.text for s in sentences])
    
    if not full_text.strip():
        return schemas.CharacterSentimentAnalysisResponse(characters=[])
    
    # Calculate total sentences for position normalization
    total_sentences_in_scope = len(sentences)
    
    # Get characters to analyze
    if request.character_ids:
        characters = db.query(models.Character).filter(
            models.Character.document_id == request.document_id,
            models.Character.id.in_(request.character_ids)
        ).all()
    else:
        characters = db.query(models.Character).filter(
            models.Character.document_id == request.document_id
        ).all()
    
    # If no characters are defined, discover them using LLM
    discovered_characters = []
    if not characters:
        print("No characters defined, discovering characters using LLM...")
        discovered_chars = await discover_characters_in_text(full_text)
        
        # Create temporary character objects for discovered characters
        for char_data in discovered_chars:
            discovered_characters.append({
                'id': f"discovered_{char_data.get('name', '').lower().replace(' ', '_')}",
                'name': char_data.get('name', 'Unknown'),
                'emoji': '👤',  # Default emoji
                'aliases': char_data.get('aliases', [])
            })
        
        characters_to_analyze = discovered_characters
    else:
        characters_to_analyze = [{
            'id': char.id,
            'name': char.name,
            'emoji': char.emoji,
            'aliases': json.loads(char.aliases) if char.aliases else []
        } for char in characters]
    
    if not characters_to_analyze:
        return schemas.CharacterSentimentAnalysisResponse(characters=[])
    
    # Analyze sentiment for each character IN PARALLEL for better performance
    import asyncio
    
    async def analyze_single_character(char_data):
        """Analyze sentiment for a single character and return the result."""
        try:
            # Analyze sentiment using AI
            sentiment_result = await analyze_character_sentiment(
                text=full_text,
                character_name=char_data['name'],
                character_aliases=char_data.get('aliases', [])
            )
            
            # Build mentions list
            mentions = []
            for mention_data in sentiment_result.get("mentions", []):
                sentence_text = mention_data.get("sentence_text", "")
                ai_sentence_index = mention_data.get("sentence_index", 0)
                ai_position = mention_data.get("position", 0.0)
                
                # PRIORITY 1: Use AI-provided sentence_index if it's valid
                # The AI analyzes the text in order, so its index should match our filtered sentence order
                actual_sentence_index = ai_sentence_index
                
                # Validate and clamp the index
                if actual_sentence_index < 0 or actual_sentence_index >= total_sentences_in_scope:
                    # If AI index is out of range, try to find by text matching
                    # But use position to find the closest match when there are duplicates
                    if sentence_text and ai_position is not None:
                        # Find sentence closest to the expected position
                        target_index = int(ai_position * (total_sentences_in_scope - 1)) if total_sentences_in_scope > 1 else 0
                        target_index = max(0, min(target_index, total_sentences_in_scope - 1))
                        
                        # Search around the target position for text match
                        search_range = min(5, total_sentences_in_scope)  # Search ±5 sentences
                        start_idx = max(0, target_index - search_range)
                        end_idx = min(total_sentences_in_scope, target_index + search_range + 1)
                        
                        for idx in range(start_idx, end_idx):
                            if idx < len(sentences) and sentences[idx].text.strip() == sentence_text.strip():
                                actual_sentence_index = idx
                                break
                        else:
                            # If no match found, use target index as fallback
                            actual_sentence_index = target_index
                    else:
                        # Last resort: try to find by text (will find first occurrence)
                        for idx, s in enumerate(sentences):
                            if s.text.strip() == sentence_text.strip():
                                actual_sentence_index = idx
                                break
                
                # Final clamp to valid range
                actual_sentence_index = min(actual_sentence_index, total_sentences_in_scope - 1) if total_sentences_in_scope > 0 else 0
                
                # Calculate position relative to the selected scope (0.0 = first sentence, 1.0 = last sentence)
                if total_sentences_in_scope > 1:
                    position = actual_sentence_index / (total_sentences_in_scope - 1)
                else:
                    position = 0.0
                
                mentions.append(schemas.CharacterSentimentMention(
                    sentence_index=actual_sentence_index,
                    sentence_text=sentence_text,
                    sentiment=mention_data.get("sentiment", "neutral"),
                    position=position
                ))
            
            return schemas.CharacterSentimentResponse(
                character_id=char_data['id'],
                character_name=char_data['name'],
                emoji=char_data.get('emoji', '👤'),
                mention_count=len(mentions),
                positive_percentage=sentiment_result.get("positive_percentage", 0),
                neutral_percentage=sentiment_result.get("neutral_percentage", 0),
                negative_percentage=sentiment_result.get("negative_percentage", 0),
                mentions=mentions,
                trend_points=sentiment_result.get("trend_points", [])
            )
        except Exception as e:
            print(f"❌ Error analyzing character {char_data.get('name', 'unknown')}: {e}")
            # Return empty result on error
            return schemas.CharacterSentimentResponse(
                character_id=char_data['id'],
                character_name=char_data['name'],
                emoji=char_data.get('emoji', '👤'),
                mention_count=0,
                positive_percentage=0,
                neutral_percentage=0,
                negative_percentage=0,
                mentions=[],
                trend_points=[]
            )
    
    # Process all characters in parallel
    print(f"🚀 Analyzing sentiment for {len(characters_to_analyze)} characters in parallel...")
    character_sentiments = await asyncio.gather(*[analyze_single_character(char_data) for char_data in characters_to_analyze])
    
    return schemas.CharacterSentimentAnalysisResponse(characters=character_sentiments)
