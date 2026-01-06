"""Character management endpoints - SINGLE SOURCE OF TRUTH for emoji system."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/documents/{document_id}/characters", tags=["characters"])


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
    
    # Create character
    db_character = models.Character(
        document_id=document_id,
        name=character.name,
        emoji=character.emoji,
        color=character.color,
        aliases=json.dumps(character.aliases or []),
        description=character.description
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
    
    # Count character references (structured)
    usage_counts = {}
    for sentence in sentences:
        char_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
        for char_id in char_refs:
            usage_counts[char_id] = usage_counts.get(char_id, 0) + 1
    
    # Count raw emoji usage (unstructured)
    raw_emoji_counts = {}
    for sentence in sentences:
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        for emoji in emojis:
            # Skip if this emoji belongs to a character
            is_character_emoji = any(c.emoji == emoji for c in characters)
            if not is_character_emoji:
                raw_emoji_counts[emoji] = raw_emoji_counts.get(emoji, 0) + 1
    
    # Build dictionary entries
    entries = []
    
    # Add character-based emojis (structured)
    for c in characters:
        entries.append(schemas.EmojiDictionaryEntry(
            emoji=c.emoji,
            character_name=c.name,
            character_id=c.id,
            color=c.color,
            usage_count=usage_counts.get(c.id, 0)
        ))
    
    # Add raw emojis (unstructured) - infer meaning from context
    for emoji, count in raw_emoji_counts.items():
        entries.append(schemas.EmojiDictionaryEntry(
            emoji=emoji,
            character_name=f"Undefined ({emoji})",  # Placeholder name
            character_id=None,  # No character definition yet
            color="#999999",  # Gray for undefined
            usage_count=count
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
    updated_count = 0
    
    for sentence in sentences:
        text_lower = sentence.text.lower()
        
        # Check if character is mentioned (name or aliases)
        is_mentioned = (
            character.name.lower() in text_lower or
            any(alias.lower() in text_lower for alias in aliases)
        )
        
        if not is_mentioned:
            continue
        
        # Parse existing data
        emojis = json.loads(sentence.emojis) if sentence.emojis else []
        char_refs = json.loads(sentence.character_refs) if sentence.character_refs else []
        
        # Add character reference if not already present
        if character_id not in char_refs:
            char_refs.append(character_id)
        
        # Add character emoji if not already present
        if character.emoji not in emojis:
            emojis.append(character.emoji)
        
        # Save updates (PRESERVES all existing emojis and refs)
        sentence.emojis = json.dumps(emojis)
        sentence.character_refs = json.dumps(char_refs)
        updated_count += 1
    
    db.commit()
    
    return {
        "character_id": character_id,
        "character_name": character.name,
        "sentences_updated": updated_count,
        "message": f"Normalized {updated_count} sentence(s) containing '{character.name}'"
    }


