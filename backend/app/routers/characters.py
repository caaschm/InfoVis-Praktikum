"""Character management endpoints - SINGLE SOURCE OF TRUTH for emoji system."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/documents/{document_id}/characters", tags=["characters"])


def _infer_emoji_meaning(emoji: str, contexts: list[str]) -> str:
    """
    Infer what an emoji represents based on the contexts where it's used.
    Uses simple keyword analysis (could be enhanced with real AI later).
    """
    if not contexts:
        return "No usage context available"
    
    # Simple heuristic-based analysis
    # Combine all contexts
    combined_text = " ".join(contexts).lower()
    
    # Common emoji meanings based on typical usage patterns
    emoji_hints = {
        "⚡": ["conflict", "tension", "fight", "battle", "sudden", "shock"],
        "🌟": ["achievement", "success", "magic", "special", "important"],
        "💔": ["sad", "heartbreak", "loss", "grief", "pain"],
        "🔥": ["intense", "passion", "anger", "hot", "burning"],
        "🌊": ["flow", "emotion", "overwhelming", "water", "deep"],
        "🎭": ["pretend", "act", "fake", "mask", "performance"],
        "💎": ["valuable", "treasure", "precious", "rare"],
        "🗡️": ["weapon", "fight", "combat", "war", "battle"],
        "🏰": ["castle", "fortress", "palace", "royal", "kingdom"],
        "🌙": ["night", "dark", "dream", "sleep", "mysterious"],
        "☀️": ["day", "bright", "hope", "warm", "light"],
        "🌈": ["hope", "promise", "beauty", "after storm", "peace"],
    }
    
    # Check if any hints match
    if emoji in emoji_hints:
        for hint in emoji_hints[emoji]:
            if hint in combined_text:
                return f"Represents {hint} in the story"
    
    # Default: describe based on frequency and context length
    if len(contexts) == 1:
        return f"Used in: \"{contexts[0][:50]}...\""
    else:
        return f"Used {len(contexts)} times throughout the story"


@router.post("/", response_model=schemas.CharacterResponse, status_code=status.HTTP_201_CREATED)
def create_character(
    document_id: str,
    character: schemas.CharacterCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new character/subject definition.
    
    This is the ONLY way to define emojis in the system.
    All emoji rendering derives from character definitions.
    """
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check for existing character with same name OR same emoji in this document
    existing_character = db.query(models.Character).filter(
        models.Character.document_id == document_id,
        ((models.Character.name.ilike(character.name.strip())) | 
         (models.Character.emoji == character.emoji))
    ).first()
    
    if existing_character:
        # If exact match, return existing character
        if existing_character.name.lower() == character.name.lower().strip() and existing_character.emoji == character.emoji:
            return schemas.CharacterResponse(
                id=existing_character.id,
                document_id=existing_character.document_id,
                name=existing_character.name,
                emoji=existing_character.emoji,
                color=existing_character.color,
                aliases=json.loads(existing_character.aliases) if existing_character.aliases else [],
                description=existing_character.description,
                word_phrases=json.loads(existing_character.word_phrases) if existing_character.word_phrases and existing_character.word_phrases != 'null' else [],
                created_at=existing_character.created_at
            )
        # If name or emoji conflict, raise error
        elif existing_character.name.lower() == character.name.lower().strip():
            raise HTTPException(status_code=409, detail=f"Character with name '{character.name}' already exists")
        else:
            raise HTTPException(status_code=409, detail=f"Character with emoji '{character.emoji}' already exists")
    
    # Aggregate word phrases from sentence emoji_mappings if not provided
    word_phrases = character.word_phrases or []
    if not word_phrases and character.emoji:
        # Collect all phrases associated with this emoji across all sentences
        sentences = db.query(models.Sentence).filter(
            models.Sentence.document_id == document_id
        ).all()
        
        phrases_set = set()
        for sentence in sentences:
            if sentence.emoji_mappings:
                try:
                    emoji_mappings = json.loads(sentence.emoji_mappings)
                    if character.emoji in emoji_mappings:
                        phrases = emoji_mappings[character.emoji]
                        if isinstance(phrases, list):
                            phrases_set.update(phrases)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        word_phrases = list(phrases_set)
    
    # Create character
    db_character = models.Character(
        document_id=document_id,
        name=character.name,
        emoji=character.emoji,
        color=character.color,
        aliases=json.dumps(character.aliases or []),
        description=character.description,
        word_phrases=json.dumps(word_phrases)
    )
    
    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    
    return schemas.CharacterResponse(
        id=db_character.id,
        document_id=db_character.document_id,
        name=db_character.name,
        emoji=db_character.emoji,
        color=db_character.color,
        aliases=json.loads(db_character.aliases) if db_character.aliases else [],
        description=db_character.description,
        word_phrases=json.loads(db_character.word_phrases) if db_character.word_phrases and db_character.word_phrases != 'null' else [],
        created_at=db_character.created_at
    )


@router.get("/", response_model=List[schemas.CharacterResponse])
def list_characters(
    document_id: str,
    db: Session = Depends(get_db)
):
    """List all characters for a document."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    characters = db.query(models.Character).filter(
        models.Character.document_id == document_id
    ).order_by(models.Character.created_at).all()
    
    return [
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


@router.get("/emoji-dictionary", response_model=schemas.EmojiDictionaryResponse)
def get_emoji_dictionary(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the emoji dictionary - AUTO-DERIVED from actual usage.
    
    Shows TWO types of emojis:
    1. Structured: Emojis from defined Characters (with names, colors)
    2. Unstructured: Raw emojis from free generation (inferred meaning)
    
    This supports the workflow: generate freely → define structure later.
    """
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all characters (structured emojis)
    characters = db.query(models.Character).filter(
        models.Character.document_id == document_id
    ).all()
    
    # Get all sentences to count usage
    sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    ).all()
    
    # Count character references (structured) and track sentences
    usage_counts = {}
    character_sentences = {}  # Track which sentences use each character
    for sentence in sentences:
        char_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
        for char_id in char_refs:
            usage_counts[char_id] = usage_counts.get(char_id, 0) + 1
            if char_id not in character_sentences:
                character_sentences[char_id] = []
            character_sentences[char_id].append(sentence.id)
    
    # Count raw emoji usage (unstructured) and track sentences
    raw_emoji_counts = {}
    raw_emoji_sentences = {}  # Track which sentences use each raw emoji
    raw_emoji_contexts = {}  # Track sentence texts for AI analysis
    for sentence in sentences:
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        for emoji in emojis:
            # Skip if this emoji belongs to a character
            is_character_emoji = any(c.emoji == emoji for c in characters)
            if not is_character_emoji:
                raw_emoji_counts[emoji] = raw_emoji_counts.get(emoji, 0) + 1
                if emoji not in raw_emoji_sentences:
                    raw_emoji_sentences[emoji] = []
                    raw_emoji_contexts[emoji] = []
                raw_emoji_sentences[emoji].append(sentence.id)
                raw_emoji_contexts[emoji].append(sentence.text)
    
    # Build dictionary entries
    entries = []
    
    # SECTION 1: Character-based emojis (structured) - ALWAYS include these
    for c in characters:
        meaning = f"Represents {c.name}" + (f": {c.description}" if c.description else "")
        entries.append(schemas.EmojiDictionaryEntry(
            emoji=c.emoji,
            character_name=c.name,
            character_id=c.id,
            color=c.color,
            usage_count=usage_counts.get(c.id, 0),
            meaning=meaning,
            sentence_ids=character_sentences.get(c.id, [])
        ))
    
    # SECTION 2: Frequently used raw emojis (unstructured)
    # Only include emojis used 2+ times to avoid clutter
    MIN_USAGE_THRESHOLD = 2
    MAX_UNASSIGNED_EMOJIS = 10  # Limit to top 10 most frequent
    
    # Sort raw emojis by usage count (most frequent first)
    frequent_emojis = sorted(
        [(emoji, count) for emoji, count in raw_emoji_counts.items() if count >= MIN_USAGE_THRESHOLD],
        key=lambda x: x[1],
        reverse=True
    )[:MAX_UNASSIGNED_EMOJIS]
    
    for emoji, count in frequent_emojis:
        # Analyze contexts to infer meaning
        contexts = raw_emoji_contexts.get(emoji, [])
        meaning = _infer_emoji_meaning(emoji, contexts)
        
        entries.append(schemas.EmojiDictionaryEntry(
            emoji=emoji,
            character_name=f"Recurring theme",
            character_id=None,
            color="#999999",  # Gray for undefined
            usage_count=count,
            meaning=meaning,
            sentence_ids=raw_emoji_sentences.get(emoji, [])
        ))
    
    return schemas.EmojiDictionaryResponse(
        document_id=document_id,
        entries=entries
    )


@router.get("/{character_id}", response_model=schemas.CharacterResponse)
def get_character(
    document_id: str,
    character_id: str,
    db: Session = Depends(get_db)
):
    """Get a single character definition."""
    character = db.query(models.Character).filter(
        models.Character.id == character_id,
        models.Character.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    return schemas.CharacterResponse(
        id=character.id,
        document_id=character.document_id,
        name=character.name,
        emoji=character.emoji,
        color=character.color,
        aliases=json.loads(character.aliases) if character.aliases else [],
        description=character.description,
        created_at=character.created_at
    )


@router.patch("/{character_id}", response_model=schemas.CharacterResponse)
def update_character(
    document_id: str,
    character_id: str,
    character_update: schemas.CharacterUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a character definition.
    
    When a character's emoji changes, all text automatically re-renders
    because text stores character references, not literal emojis.
    """
    character = db.query(models.Character).filter(
        models.Character.id == character_id,
        models.Character.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    # Update fields if provided
    if character_update.name is not None:
        character.name = character_update.name
    if character_update.emoji is not None:
        character.emoji = character_update.emoji
    if character_update.color is not None:
        character.color = character_update.color
    if character_update.aliases is not None:
        character.aliases = json.dumps(character_update.aliases)
    if character_update.description is not None:
        character.description = character_update.description
    if character_update.word_phrases is not None:
        character.word_phrases = json.dumps(character_update.word_phrases)
    
    db.commit()
    db.refresh(character)
    
    return schemas.CharacterResponse(
        id=character.id,
        document_id=character.document_id,
        name=character.name,
        emoji=character.emoji,
        color=character.color,
        aliases=json.loads(character.aliases) if character.aliases else [],
        description=character.description,
        word_phrases=json.loads(character.word_phrases) if character.word_phrases and character.word_phrases != 'null' else [],
        created_at=character.created_at
    )


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(
    document_id: str,
    character_id: str,
    db: Session = Depends(get_db)
):
    """Delete a character definition."""
    character = db.query(models.Character).filter(
        models.Character.id == character_id,
        models.Character.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    db.delete(character)
    db.commit()
    
    return None


@router.post("/{character_id}/normalize", status_code=status.HTTP_200_OK)
def normalize_character_in_sentences(
    document_id: str,
    character_id: str,
    db: Session = Depends(get_db)
):
    """
    Selectively normalize character references in sentences where mentioned.
    
    NON-DESTRUCTIVE: Only updates sentences that mention this character.
    Preserves all other emojis and character references.
    """
    # Verify character exists
    character = db.query(models.Character).filter(
        models.Character.id == character_id,
        models.Character.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    # Get all sentences in the document
    sentences = db.query(models.Sentence).filter(
        models.Sentence.document_id == document_id
    ).all()
    
    aliases = json.loads(character.aliases) if character.aliases else []
    word_phrases = json.loads(character.word_phrases) if character.word_phrases else []
    updated_count = 0
    
    # Create set of all words/phrases that belong to this character
    character_words = set()
    character_words.add(character.name.lower())
    character_words.update([alias.lower() for alias in aliases])
    character_words.update([phrase.lower() for phrase in word_phrases])
    
    for sentence in sentences:
        # Parse existing data first
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        char_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
        emoji_mappings = json.loads(sentence.emoji_mappings) if sentence.emoji_mappings else {}
        
        sentence_updated = False
        
        # Check TWO conditions:
        # 1. Character emoji is already in the sentence (from AI generation)
        # 2. Character name/aliases are mentioned in the text
        has_emoji = character.emoji in emojis
        
        text_lower = sentence.text.lower()
        is_mentioned = (
            character.name.lower() in text_lower or
            any(alias.lower() in text_lower for alias in aliases)
        )
        
        # If either condition is met, add character references
        if has_emoji or is_mentioned:
            # Add character reference if not already present
            if character_id not in char_refs:
                char_refs.append(character_id)
                sentence_updated = True
            
            # Add character emoji if not already present
            if character.emoji not in emojis:
                emojis.append(character.emoji)
                sentence_updated = True
        
        # ALWAYS clean up emoji mappings in ALL sentences (prevent contamination)
        mappings_updated = False
        
        # Step 1: Find any emoji mappings that contain this character's words
        # and migrate them to the correct character emoji
        for emoji_key in list(emoji_mappings.keys()):
            if emoji_key in emoji_mappings:
                original_phrases = emoji_mappings[emoji_key]
                if isinstance(original_phrases, list):
                    # Find phrases that belong to this character
                    character_phrases = [
                        phrase for phrase in original_phrases 
                        if phrase.lower() in character_words
                    ]
                    # Find phrases that don't belong to this character
                    other_phrases = [
                        phrase for phrase in original_phrases 
                        if phrase.lower() not in character_words
                    ]
                    
                    # If this emoji has character phrases but wrong emoji key, migrate them
                    if character_phrases and emoji_key != character.emoji:
                        mappings_updated = True
                        # Move character phrases to correct emoji
                        if character.emoji not in emoji_mappings:
                            emoji_mappings[character.emoji] = []
                        emoji_mappings[character.emoji].extend(character_phrases)
                        # Remove duplicates
                        emoji_mappings[character.emoji] = list(set(emoji_mappings[character.emoji]))
                        
                        # Update old emoji with remaining phrases
                        if other_phrases:
                            emoji_mappings[emoji_key] = other_phrases
                        else:
                            # Remove empty mapping
                            del emoji_mappings[emoji_key]
                    
                    # If correct emoji but has character phrases, clean them out 
                    # (they belong to character, not emoji mapping)
                    elif character_phrases and emoji_key == character.emoji:
                        # Remove character phrases from emoji mapping to prevent contamination
                        if other_phrases:
                            emoji_mappings[emoji_key] = other_phrases
                            mappings_updated = True
                        elif len(original_phrases) > len(other_phrases):
                            # Had character phrases but now empty
                            del emoji_mappings[emoji_key] 
                            mappings_updated = True
        
        # Save updates if anything changed
        if sentence_updated or mappings_updated:
            sentence.emojis = json.dumps(emojis)
            sentence.character_refs = json.dumps(char_refs)
            sentence.emoji_mappings = json.dumps(emoji_mappings)
            updated_count += 1
    
    db.commit()
    
    return {
        "character_id": character_id,
        "character_name": character.name,
        "sentences_updated": updated_count,
        "message": f"Normalized {updated_count} sentence(s) containing '{character.name}'"
    }
    
@router.delete("/cleanup-duplicates", status_code=status.HTTP_200_OK)
def cleanup_duplicate_characters(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Remove duplicate characters, keeping the one with most word_phrases."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all characters for this document
    characters = db.query(models.Character).filter(
        models.Character.document_id == document_id
    ).all()
    
    # Group by name + emoji combination
    character_groups = {}
    for char in characters:
        key = (char.name.lower().strip(), char.emoji)
        if key not in character_groups:
            character_groups[key] = []
        character_groups[key].append(char)
    
    removed_count = 0
    kept_characters = []
    
    # For each group, keep the best character and delete others
    for (name, emoji), group in character_groups.items():
        if len(group) > 1:
            # Sort by: 1) most word_phrases, 2) most aliases, 3) newest
            group.sort(key=lambda c: (
                len(json.loads(c.word_phrases) if c.word_phrases and c.word_phrases != 'null' else []),
                len(json.loads(c.aliases) if c.aliases else []),
                c.created_at
            ), reverse=True)
            
            # Keep the best one
            best_character = group[0]
            kept_characters.append(best_character.id)
            
            # Delete the others
            for char in group[1:]:
                db.delete(char)
                removed_count += 1
        else:
            # No duplicates, keep it
            kept_characters.append(group[0].id)
    
    db.commit()
    
    return {
        "removed_duplicates": removed_count,
        "remaining_characters": len(kept_characters),
        "message": f"Removed {removed_count} duplicate characters"
    }


