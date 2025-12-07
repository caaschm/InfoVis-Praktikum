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
