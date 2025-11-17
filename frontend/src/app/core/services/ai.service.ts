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
    TextFromEmojisResponse
} from '../models/document.model';

@Injectable({
    providedIn: 'root'
})
export class AiService {
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
}
