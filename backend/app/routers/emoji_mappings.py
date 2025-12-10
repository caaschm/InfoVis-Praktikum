"""Enhanced emoji mapping endpoints - word-level, custom sets, and character definitions."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/documents/{document_id}/emoji-mappings", tags=["emoji-mappings"])


# ========== Word Emoji Mappings ==========

@router.get("/words", response_model=list[schemas.WordEmojiMappingResponse])
def get_word_mappings(document_id: str, db: Session = Depends(get_db)):
    """Get all word-emoji mappings for a document."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    mappings = db.query(models.WordEmojiMapping).filter(
        models.WordEmojiMapping.document_id == document_id
    ).all()
    
    return [
        schemas.WordEmojiMappingResponse(
            id=m.id,
            document_id=m.document_id,
            word_pattern=m.word_pattern,
            emoji=m.emoji,
            is_active=bool(m.is_active),
            created_at=m.created_at
        ) for m in mappings
    ]


@router.post("/words", response_model=schemas.WordEmojiMappingResponse, status_code=status.HTTP_201_CREATED)
def create_word_mapping(
    document_id: str,
    mapping: schemas.WordEmojiMappingCreate,
    db: Session = Depends(get_db)
):
    """Create a new word-emoji mapping."""
    # Verify document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check for duplicate word pattern
    existing = db.query(models.WordEmojiMapping).filter(
        models.WordEmojiMapping.document_id == document_id,
        models.WordEmojiMapping.word_pattern == mapping.word_pattern.lower()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Mapping for word '{mapping.word_pattern}' already exists"
        )
    
    new_mapping = models.WordEmojiMapping(
        document_id=document_id,
        word_pattern=mapping.word_pattern.lower(),
        emoji=mapping.emoji,
        is_active=1 if mapping.is_active else 0
    )
    
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)
    
    return schemas.WordEmojiMappingResponse(
        id=new_mapping.id,
        document_id=new_mapping.document_id,
        word_pattern=new_mapping.word_pattern,
        emoji=new_mapping.emoji,
        is_active=bool(new_mapping.is_active),
        created_at=new_mapping.created_at
    )


@router.patch("/words/{mapping_id}", response_model=schemas.WordEmojiMappingResponse)
def update_word_mapping(
    document_id: str,
    mapping_id: str,
    update: schemas.WordEmojiMappingUpdate,
    db: Session = Depends(get_db)
):
    """Update a word-emoji mapping."""
    mapping = db.query(models.WordEmojiMapping).filter(
        models.WordEmojiMapping.id == mapping_id,
        models.WordEmojiMapping.document_id == document_id
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    if update.word_pattern is not None:
        mapping.word_pattern = update.word_pattern.lower()
    if update.emoji is not None:
        mapping.emoji = update.emoji
    if update.is_active is not None:
        mapping.is_active = 1 if update.is_active else 0
    
    db.commit()
    db.refresh(mapping)
    
    return schemas.WordEmojiMappingResponse(
        id=mapping.id,
        document_id=mapping.document_id,
        word_pattern=mapping.word_pattern,
        emoji=mapping.emoji,
        is_active=bool(mapping.is_active),
        created_at=mapping.created_at
    )


@router.delete("/words/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word_mapping(
    document_id: str,
    mapping_id: str,
    db: Session = Depends(get_db)
):
    """Delete a word-emoji mapping."""
    mapping = db.query(models.WordEmojiMapping).filter(
        models.WordEmojiMapping.id == mapping_id,
        models.WordEmojiMapping.document_id == document_id
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    db.delete(mapping)
    db.commit()
    
    return None


# ========== Custom Emoji Sets ==========

@router.get("/sets", response_model=list[schemas.CustomEmojiSetResponse])
def get_custom_emoji_sets(document_id: str, db: Session = Depends(get_db)):
    """Get all custom emoji sets for a document."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    sets = db.query(models.CustomEmojiSet).filter(
        models.CustomEmojiSet.document_id == document_id
    ).all()
    
    return [
        schemas.CustomEmojiSetResponse(
            id=s.id,
            document_id=s.document_id,
            name=s.name,
            emojis=json.loads(s.emojis),
            is_default=bool(s.is_default),
            created_at=s.created_at
        ) for s in sets
    ]


@router.post("/sets", response_model=schemas.CustomEmojiSetResponse, status_code=status.HTTP_201_CREATED)
def create_custom_emoji_set(
    document_id: str,
    emoji_set: schemas.CustomEmojiSetCreate,
    db: Session = Depends(get_db)
):
    """Create a new custom emoji set."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # If this is marked as default, unset any existing default
    if emoji_set.is_default:
        db.query(models.CustomEmojiSet).filter(
            models.CustomEmojiSet.document_id == document_id,
            models.CustomEmojiSet.is_default == 1
        ).update({models.CustomEmojiSet.is_default: 0})
    
    new_set = models.CustomEmojiSet(
        document_id=document_id,
        name=emoji_set.name,
        emojis=json.dumps(emoji_set.emojis),
        is_default=1 if emoji_set.is_default else 0
    )
    
    db.add(new_set)
    db.commit()
    db.refresh(new_set)
    
    return schemas.CustomEmojiSetResponse(
        id=new_set.id,
        document_id=new_set.document_id,
        name=new_set.name,
        emojis=json.loads(new_set.emojis),
        is_default=bool(new_set.is_default),
        created_at=new_set.created_at
    )


@router.patch("/sets/{set_id}", response_model=schemas.CustomEmojiSetResponse)
def update_custom_emoji_set(
    document_id: str,
    set_id: str,
    update: schemas.CustomEmojiSetUpdate,
    db: Session = Depends(get_db)
):
    """Update a custom emoji set."""
    emoji_set = db.query(models.CustomEmojiSet).filter(
        models.CustomEmojiSet.id == set_id,
        models.CustomEmojiSet.document_id == document_id
    ).first()
    
    if not emoji_set:
        raise HTTPException(status_code=404, detail="Emoji set not found")
    
    if update.name is not None:
        emoji_set.name = update.name
    if update.emojis is not None:
        emoji_set.emojis = json.dumps(update.emojis)
    if update.is_default is not None:
        if update.is_default:
            # Unset other defaults
            db.query(models.CustomEmojiSet).filter(
                models.CustomEmojiSet.document_id == document_id,
                models.CustomEmojiSet.id != set_id
            ).update({models.CustomEmojiSet.is_default: 0})
        emoji_set.is_default = 1 if update.is_default else 0
    
    db.commit()
    db.refresh(emoji_set)
    
    return schemas.CustomEmojiSetResponse(
        id=emoji_set.id,
        document_id=emoji_set.document_id,
        name=emoji_set.name,
        emojis=json.loads(emoji_set.emojis),
        is_default=bool(emoji_set.is_default),
        created_at=emoji_set.created_at
    )


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_emoji_set(
    document_id: str,
    set_id: str,
    db: Session = Depends(get_db)
):
    """Delete a custom emoji set."""
    emoji_set = db.query(models.CustomEmojiSet).filter(
        models.CustomEmojiSet.id == set_id,
        models.CustomEmojiSet.document_id == document_id
    ).first()
    
    if not emoji_set:
        raise HTTPException(status_code=404, detail="Emoji set not found")
    
    db.delete(emoji_set)
    db.commit()
    
    return None


# ========== Character Definitions ==========

@router.get("/characters", response_model=list[schemas.CharacterDefinitionResponse])
def get_character_definitions(document_id: str, db: Session = Depends(get_db)):
    """Get all character definitions for a document."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    characters = db.query(models.CharacterDefinition).filter(
        models.CharacterDefinition.document_id == document_id
    ).all()
    
    return [
        schemas.CharacterDefinitionResponse(
            id=c.id,
            document_id=c.document_id,
            name=c.name,
            emoji=c.emoji,
            aliases=json.loads(c.aliases) if c.aliases else [],
            description=c.description,
            color=c.color,
            created_at=c.created_at
        ) for c in characters
    ]


@router.post("/characters", response_model=schemas.CharacterDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_character_definition(
    document_id: str,
    character: schemas.CharacterDefinitionCreate,
    db: Session = Depends(get_db)
):
    """Create a new character definition."""
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    new_character = models.CharacterDefinition(
        document_id=document_id,
        name=character.name,
        emoji=character.emoji,
        aliases=json.dumps(character.aliases) if character.aliases else json.dumps([]),
        description=character.description,
        color=character.color
    )
    
    db.add(new_character)
    db.commit()
    db.refresh(new_character)
    
    return schemas.CharacterDefinitionResponse(
        id=new_character.id,
        document_id=new_character.document_id,
        name=new_character.name,
        emoji=new_character.emoji,
        aliases=json.loads(new_character.aliases) if new_character.aliases else [],
        description=new_character.description,
        color=new_character.color,
        created_at=new_character.created_at
    )


@router.patch("/characters/{character_id}", response_model=schemas.CharacterDefinitionResponse)
def update_character_definition(
    document_id: str,
    character_id: str,
    update: schemas.CharacterDefinitionUpdate,
    db: Session = Depends(get_db)
):
    """Update a character definition."""
    character = db.query(models.CharacterDefinition).filter(
        models.CharacterDefinition.id == character_id,
        models.CharacterDefinition.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    if update.name is not None:
        character.name = update.name
    if update.emoji is not None:
        character.emoji = update.emoji
    if update.aliases is not None:
        character.aliases = json.dumps(update.aliases)
    if update.description is not None:
        character.description = update.description
    if update.color is not None:
        character.color = update.color
    
    db.commit()
    db.refresh(character)
    
    return schemas.CharacterDefinitionResponse(
        id=character.id,
        document_id=character.document_id,
        name=character.name,
        emoji=character.emoji,
        aliases=json.loads(character.aliases) if character.aliases else [],
        description=character.description,
        color=character.color,
        created_at=character.created_at
    )


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character_definition(
    document_id: str,
    character_id: str,
    db: Session = Depends(get_db)
):
    """Delete a character definition."""
    character = db.query(models.CharacterDefinition).filter(
        models.CharacterDefinition.id == character_id,
        models.CharacterDefinition.document_id == document_id
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    db.delete(character)
    db.commit()
    
    return None
