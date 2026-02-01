/**
 * AI service - handles AI-powered features
 * Calls backend AI endpoints for emoji and text generation
 */
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import {
    CharacterSuggestionRequest,
    CharacterSuggestionResponse,
    TextFromCharactersRequest,
    TextFromCharactersResponse,
    SpiderChartAnalysisRequest,
    SpiderChartAnalysisResponse, SpiderChartIntentRequest, SpiderChartIntentResponse,
    StoryArcResponse,
    ReformulateSentenceRequest,
    ReformulateSentenceResponse,
    CharacterSentimentAnalysisRequest,
    CharacterSentimentAnalysisResponse,
    RewriteSentenceSentimentRequest,
    RewriteSentenceSentimentResponse
} from '../models/document.model';

export interface SpiderIntentRequest {
    documentId: number | string;
    text: string;
    dimension: 'drama' | 'humor' | 'conflict' | 'mystery';
    baselineValue: number;
    currentValue: number;
}

export interface SpiderIntentResponse {
    summary: string;
    ideas: string[];
    preview: string;
}

@Injectable({
    providedIn: 'root'
})
export class AiService {
    private http: any;
    constructor(private apiService: ApiService) { }

    /**
     * Suggest characters mentioned in the sentence text
     */
    suggestCharacters(request: CharacterSuggestionRequest): Observable<CharacterSuggestionResponse> {
        return this.apiService.post<CharacterSuggestionResponse>(
            '/api/ai/suggest-characters',
            request
        );
    }

    /**
     * Generate text from selected characters
     */
    generateTextFromCharacters(request: TextFromCharactersRequest): Observable<TextFromCharactersResponse> {
        return this.apiService.post<TextFromCharactersResponse>(
            '/api/ai/text-from-characters',
            request
        );
    }

    // DEPRECATED - kept for compatibility during migration
    generateEmojisFromText(request: any): Observable<any> {
        // Map to character suggestion for now
        return this.apiService.post<any>(
            '/api/ai/suggest-characters',
            request
        );
    }

    generateTextFromEmojis(request: any): Observable<any> {
        // Map to character-based generation
        return this.apiService.post<any>(
            '/api/ai/text-from-characters',
            request
        );
    }

    /**
     * Analyze text for spider chart values (drama, humor, conflict, mystery)
     */
    analyzeSpiderChart(request: SpiderChartAnalysisRequest): Observable<SpiderChartAnalysisResponse> {
        return this.apiService.post<SpiderChartAnalysisResponse>(
            '/api/ai/analyze-spider-chart',
            request
        );
    }

    getSpiderIntent(payload: SpiderIntentRequest): Observable<SpiderIntentResponse> {
        return this.apiService.post<SpiderIntentResponse>('/api/ai/spider-intent', {
            documentId: payload.documentId,
            text: payload.text,
            dimension: payload.dimension,
            baselineValue: payload.baselineValue,
            currentValue: payload.currentValue,
        });
    }

    getStoryArc(payload: { documentId?: number | string; text?: string; granularity?: number }) {
        return this.apiService.post<StoryArcResponse>('/api/ai/story-arc', payload);
    }

  reformulateSentenceForTension(request: ReformulateSentenceRequest): Observable<ReformulateSentenceResponse> {
    return this.apiService.post<ReformulateSentenceResponse>(
      '/api/ai/reformulate-sentence-tension',
      request
    );
  }

  /**
   * Analyze character sentiment in the document
   */
  analyzeCharacterSentiment(request: CharacterSentimentAnalysisRequest): Observable<CharacterSentimentAnalysisResponse> {
    return this.apiService.post<CharacterSentimentAnalysisResponse>(
      '/api/ai/analyze-character-sentiment',
      request
    );
  }

  /**
   * Rewrite a sentence toward a target character sentiment (positive, neutral, negative).
   * Used by the Character Sentiment suggestions panel.
   */
  rewriteSentenceForSentiment(request: RewriteSentenceSentimentRequest): Observable<RewriteSentenceSentimentResponse> {
    return this.apiService.post<RewriteSentenceSentimentResponse>(
      '/api/ai/rewrite-sentence-sentiment',
      request
    );
  }

  /**
   * Clear character sentiment cache only (not emoji cache) so the next analysis uses fresh data.
   */
  clearCharacterSentimentCache(): Observable<{ status: string; caches?: string[] }> {
    return this.apiService.post<{ status: string; caches?: string[] }>(
      '/api/ai/clear-cache?character_sentiment=true&character_emoji=false',
      {}
    );
  }

}
