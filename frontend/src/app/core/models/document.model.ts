/**
 * Core domain models for Plottery
 * 
 * CONSOLIDATED EMOJI SYSTEM:
 * - Characters are the SINGLE SOURCE OF TRUTH for all emojis
 * - Sentences store character references, not literal emojis
 * - Text rendering is reactive - changing a character's emoji updates all text
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
    chapterId?: string | null;  // Optional chapter assignment
    index: number;
    text: string;
    characterRefs: string[];  // Array of character IDs
    emojis: string[];  // Raw emoji strings
    emojiMappings?: { [emoji: string]: string[] };  // Maps emoji to phrases it represents
    isAiGenerated?: boolean;  // Flag for AI-generated text
    aiCategory?: string;  // Category of AI text (drama, humor, etc.)
}

export interface Chapter {
    id: string;
    documentId: string;
    title: string;
    type?: string;
    emoji?: string | null;
    index: number;
    createdAt: string;
    updatedAt: string;
}

export interface DocumentDetail extends Document {
    sentences: Sentence[];
    characters: Character[];  // SINGLE SOURCE OF TRUTH
    chapters: Chapter[];
}

export interface DocumentMetadata {
    id: string;
    title: string;
    createdAt: string;
    updatedAt: string;
}

// ========== Character (SINGLE SOURCE OF TRUTH) ==========

export interface Character {
    id: string;
    documentId: string;
    name: string;
    emoji: string;
    color: string;  // Required hex color for highlighting
    aliases: string[];
    description?: string;
    wordPhrases: string[];  // Words/phrases this emoji represents (for highlighting)
    createdAt: string;
}

export interface CharacterCreate {
    name: string;
    emoji: string;
    color: string;
    aliases?: string[];
    description?: string;
}

export interface CharacterUpdate {
    name?: string;
    emoji?: string;
    color?: string;
    aliases?: string[];
    description?: string;
}

// ========== Emoji Dictionary (Read-Only, Auto-Derived) ==========

export interface EmojiDictionaryEntry {
    emoji: string;
    characterName: string;
    characterId: string | null;
    color: string;
    usageCount: number;
    meaning: string;
    sentenceIds: string[];
}

export interface EmojiDictionary {
    documentId: string;
    entries: EmojiDictionaryEntry[];
}

// ========== AI Integration ==========

export interface CharacterSuggestionRequest {
    documentId: string;
    sentenceId: string;
    text: string;
    characters: Character[];  // Available characters
}

export interface CharacterSuggestionResponse {
    sentenceId: string;
    emojis: string[];  // Raw emoji strings (free or structured)
    characterRefs: string[];  // Character IDs (structured only)
}

export interface TextFromCharactersRequest {
    documentId: string;
    sentenceId?: string;
    characterIds: string[];
    characters: Character[];
}

export interface TextFromCharactersResponse {
    sentenceId?: string;
    suggestedText: string;
}

// ========== DEPRECATED - Compatibility Layer ==========
// These interfaces are deprecated but kept temporarily for migration
// TODO: Remove these and update all dependent code to use Character-based system

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
// -------------------------------------- Story Arc Models --------------------------------------
export interface Beat {
  name: string;
  position: number; // 0..1 (x)
  value: number;    // 0..1 (y / tension)
  note?: string;
  sentence_index?: number;
  tensionReason?: string;
}

export interface SentenceClassification {
    index: number;
    stage: 'Exposition' | 'Rising Action' | 'Climax' | 'Falling Action' | 'Denouement';
    value?: number; // Arc value 0..1 for positioning on the arc
    significant?: boolean; // Whether the classification is significant
}

export interface StoryArcResponse {
  arc: number[]; // Werte 0..1
  beats: Beat[];
  sentence_classifications?: SentenceClassification[];
}

export interface ReformulateSentenceRequest {
  documentId: string;
  sentenceId: string;
  text: string;
  tensionValue: number; // 0..1
}

export interface ReformulateSentenceResponse {
  sentenceId: string;
  reformulatedText: string;
}