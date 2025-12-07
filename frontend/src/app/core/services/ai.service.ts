/**
 * AI service - handles AI-powered features
 * Calls backend AI endpoints for emoji and text generation
 */
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import {
  EmojiSuggestionRequest,
  EmojiSuggestionResponse,
  TextFromEmojisRequest,
  TextFromEmojisResponse,
  SpiderChartAnalysisRequest,
  SpiderChartAnalysisResponse, SpiderChartIntentRequest, SpiderChartIntentResponse
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
     * Generate emoji suggestions from sentence text
     * TODO: Fine-tune on backend for better results
     */
    generateEmojisFromText(request: EmojiSuggestionRequest): Observable<EmojiSuggestionResponse> {
        return this.apiService.post<EmojiSuggestionResponse>(
            '/api/ai/emojis-from-text',
            request
        );
    }

    /**
     * Generate text from emojis
     * TODO: Improve prompt engineering on backend for more context-aware generation
     */
    generateTextFromEmojis(request: TextFromEmojisRequest): Observable<TextFromEmojisResponse> {
        return this.apiService.post<TextFromEmojisResponse>(
            '/api/ai/text-from-emojis',
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

}
