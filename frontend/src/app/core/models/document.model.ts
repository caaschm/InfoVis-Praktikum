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
    chapterId?: string;
    index: number;
    text: string;
    emojis: string[];
}
export interface SentenceUpdate {
    text?: string;
    emojis?: string[];
    chapterId?: string;  // Add this line
}

export interface DocumentDetail extends Document {
    chapters: Chapter[];
    sentences: Sentence[];
}

export interface DocumentMetadata {
    id: string;
    title: string;
    createdAt: string;
    updatedAt: string;
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

export interface Chapter {
    id: string;
    documentId: string;
    title: string;
    index: number;
    createdAt: string;
    updatedAt: string;
}
