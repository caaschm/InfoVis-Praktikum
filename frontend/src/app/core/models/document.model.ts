/**
 * Core domain models for Plottery
 */

export interface Document {
    id: string;
    title: string;
    content: string;
    createdAt: string;
    updatedAt: string;
}

export interface Sentence {
    id: string;
    documentId: string;
    index: number;
    text: string;
    emojis: string[];
}

export interface DocumentDetail extends Document {
    sentences: Sentence[];
    wordMappings: WordEmojiMapping[];
    customEmojiSets: CustomEmojiSet[];
    characters: CharacterDefinition[];
}

export interface DocumentMetadata {
    id: string;
    title: string;
    createdAt: string;
    updatedAt: string;
}

// ========== Word Emoji Mapping ==========

export interface WordEmojiMapping {
    id: string;
    documentId: string;
    wordPattern: string;
    emoji: string;
    isActive: boolean;
    createdAt: string;
}

export interface WordEmojiMappingCreate {
    wordPattern: string;
    emoji: string;
    isActive: boolean;
}

export interface WordEmojiMappingUpdate {
    wordPattern?: string;
    emoji?: string;
    isActive?: boolean;
}

// ========== Custom Emoji Set ==========

export interface CustomEmojiSet {
    id: string;
    documentId: string;
    name: string;
    emojis: string[];
    isDefault: boolean;
    createdAt: string;
}

export interface CustomEmojiSetCreate {
    name: string;
    emojis: string[];
    isDefault: boolean;
}

export interface CustomEmojiSetUpdate {
    name?: string;
    emojis?: string[];
    isDefault?: boolean;
}

// ========== Character Definition ==========

export interface CharacterDefinition {
    id: string;
    documentId: string;
    name: string;
    emoji: string;
    aliases: string[];
    description?: string;
    color?: string;
    createdAt: string;
}

export interface CharacterDefinitionCreate {
    name: string;
    emoji: string;
    aliases?: string[];
    description?: string;
    color?: string;
}

export interface CharacterDefinitionUpdate {
    name?: string;
    emoji?: string;
    aliases?: string[];
    description?: string;
    color?: string;
}

// ========== AI Integration ==========

export interface EmojiSuggestionRequest {
    documentId: string;
    sentenceId: string;
    text: string;
}

export interface EmojiSuggestionResponse {
    sentenceId: string;
    emojis: string[];
}

export interface TextFromEmojisRequest {
    documentId: string;
    sentenceId: string | null;
    emojis: string[];
}

export interface TextFromEmojisResponse {
    sentenceId: string | null;
    suggestedText: string;
}

export interface SentenceUpdate {
    text?: string;
    emojis?: string[];
}

export interface SpiderChartAnalysisRequest {
    documentId: string;
    text: string;
}

export interface SpiderChartAnalysisResponse {
    drama: number;
    humor: number;
    conflict: number;
    mystery: number;
}

export interface SpiderChartIntentRequest {
  documentId: string;
  text: string;
  dimension: 'drama' | 'humor' | 'conflict' | 'mystery';
  currentValue: number;
  baselineValue: number;
}

export interface SpiderChartIntentResponse {
  summary: string;
  ideas: string[];
  preview: string;
}
