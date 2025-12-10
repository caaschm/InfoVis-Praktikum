"""Pydantic schemas for request/response validation."""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
import json


# ========== Document Schemas ==========

class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DocumentContentUpdate(BaseModel):
    """Schema for updating document content."""
    content: str = Field(..., min_length=1)


class DocumentMetadata(BaseModel):
    """Minimal document info for list view."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SentenceBase(BaseModel):
    """Base sentence schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    index: int
    text: str
    emojis: list[str] = Field(default_factory=list, max_length=5)


class DocumentDetail(BaseModel):
    """Full document with sentences and emojis."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    sentences: list[SentenceBase] = []
    word_mappings: list['WordEmojiMappingResponse'] = []
    custom_emoji_sets: list['CustomEmojiSetResponse'] = []
    characters: list['CharacterDefinitionResponse'] = []


# ========== Sentence Schemas ==========

class SentenceUpdate(BaseModel):
    """Schema for updating a sentence."""
    text: Optional[str] = None
    emojis: Optional[list[str]] = Field(None, max_length=5)

    @field_validator('emojis')
    @classmethod
    def validate_emoji_count(cls, v):
        """Ensure max 5 emojis."""
        if v is not None and len(v) > 5:
            raise ValueError('Maximum 5 emojis allowed per sentence')
        return v


class SentenceResponse(BaseModel):
    """Response schema for a single sentence."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    index: int
    text: str
    emojis: list[str]


# ========== AI Integration Schemas ==========

class EmojiSuggestionRequest(BaseModel):
    """Request to generate emoji suggestions from text."""
    model_config = ConfigDict(populate_by_name=True)
    
    document_id: str = Field(alias='documentId')
    sentence_id: str = Field(alias='sentenceId')
    text: str


class EmojiSuggestionResponse(BaseModel):
    """Response with emoji suggestions."""
    model_config = ConfigDict(populate_by_name=True)
    
    sentence_id: str = Field(alias='sentenceId')
    emojis: list[str] = Field(..., max_length=5)


class TextFromEmojisRequest(BaseModel):
    """Request to generate text from emojis."""
    model_config = ConfigDict(populate_by_name=True)
    
    document_id: str = Field(alias='documentId')
    sentence_id: Optional[str] = Field(default=None, alias='sentenceId')
    emojis: list[str] = Field(..., min_length=1, max_length=5)

    @field_validator('emojis')
    @classmethod
    def validate_emoji_count(cls, v):
        """Ensure 1-5 emojis."""
        if len(v) < 1 or len(v) > 5:
            raise ValueError('Must provide 1-5 emojis')
        return v


class TextFromEmojisResponse(BaseModel):
    """Response with generated text."""
    model_config = ConfigDict(populate_by_name=True)
    
    sentence_id: Optional[str] = Field(default=None, alias='sentenceId')
    suggested_text: str = Field(alias='suggestedText')


class SpiderChartAnalysisRequest(BaseModel):
    """Request to analyze text for spider chart values."""
    model_config = ConfigDict(populate_by_name=True)
    
    document_id: str = Field(alias='documentId')
    text: str  # Can be full document content or selected text


class SpiderChartAnalysisResponse(BaseModel):
    """Response with spider chart emotion/setting values."""
    model_config = ConfigDict(populate_by_name=True)
    
    drama: int = Field(..., ge=0, le=100)
    humor: int = Field(..., ge=0, le=100)
    conflict: int = Field(..., ge=0, le=100)
    mystery: int = Field(..., ge=0, le=100)

class SpiderChartIntentRequest(BaseModel):
    """Request to get suggestions for adjusting a spider chart dimension."""
    model_config = ConfigDict(populate_by_name=True)
    
    document_id: str = Field(alias='documentId')
    text: str
    dimension: str  # 'drama' | 'humor' | 'conflict' | 'mystery'
    baseline_value: int = Field(alias='baselineValue', ge=0, le=100)
    current_value: int = Field(alias='currentValue', ge=0, le=100)

class SpiderChartIntentResponse(BaseModel):
    """Response with suggestions for adjusting text to match slider intent."""
    summary: str
    ideas: list[str]
    preview: str



# ========== Health Check ==========

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime


# ========== Word Emoji Mapping Schemas ==========

class WordEmojiMappingCreate(BaseModel):
    """Schema for creating a word-emoji mapping."""
    word_pattern: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(..., min_length=1, max_length=10)
    is_active: bool = True


class WordEmojiMappingUpdate(BaseModel):
    """Schema for updating a word-emoji mapping."""
    word_pattern: Optional[str] = Field(None, min_length=1, max_length=100)
    emoji: Optional[str] = Field(None, min_length=1, max_length=10)
    is_active: Optional[bool] = None


class WordEmojiMappingResponse(BaseModel):
    """Response schema for word-emoji mapping."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    word_pattern: str
    emoji: str
    is_active: bool
    created_at: datetime


# ========== Custom Emoji Set Schemas ==========

class CustomEmojiSetCreate(BaseModel):
    """Schema for creating a custom emoji set."""
    name: str = Field(..., min_length=1, max_length=100)
    emojis: list[str] = Field(..., min_length=1)
    is_default: bool = False

    @field_validator('emojis')
    @classmethod
    def validate_emojis(cls, v):
        """Ensure at least one emoji."""
        if len(v) < 1:
            raise ValueError('Must provide at least one emoji')
        return v


class CustomEmojiSetUpdate(BaseModel):
    """Schema for updating a custom emoji set."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    emojis: Optional[list[str]] = Field(None, min_length=1)
    is_default: Optional[bool] = None

    @field_validator('emojis')
    @classmethod
    def validate_emojis(cls, v):
        """Ensure at least one emoji."""
        if v is not None and len(v) < 1:
            raise ValueError('Must provide at least one emoji')
        return v


class CustomEmojiSetResponse(BaseModel):
    """Response schema for custom emoji set."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    name: str
    emojis: list[str]
    is_default: bool
    created_at: datetime


# ========== Character Definition Schemas ==========

class CharacterDefinitionCreate(BaseModel):
    """Schema for creating a character definition."""
    name: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(..., min_length=1, max_length=10)
    aliases: Optional[list[str]] = Field(default_factory=list)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class CharacterDefinitionUpdate(BaseModel):
    """Schema for updating a character definition."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    emoji: Optional[str] = Field(None, min_length=1, max_length=10)
    aliases: Optional[list[str]] = None
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class CharacterDefinitionResponse(BaseModel):
    """Response schema for character definition."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    name: str
    emoji: str
    aliases: list[str]
    description: Optional[str]
    color: Optional[str]
    created_at: datetime
