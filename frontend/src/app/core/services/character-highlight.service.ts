import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Service to manage highlighting across components
 * Tracks which emoji is being hovered to highlight in sentences
 */
@Injectable({
    providedIn: 'root'
})
export class CharacterHighlightService {
    // Track which emoji is currently hovered (from dictionary)
    private hoveredEmojiSubject = new BehaviorSubject<string | null>(null);
    public hoveredEmoji$: Observable<string | null> = this.hoveredEmojiSubject.asObservable();

    // Track the color for highlighting
    private highlightColorSubject = new BehaviorSubject<string>('#999999');
    public highlightColor$: Observable<string> = this.highlightColorSubject.asObservable();

    // Track sentence-specific highlighting (for sentiment points)
    private highlightedSentenceIdSubject = new BehaviorSubject<string | null>(null);
    public highlightedSentenceId$: Observable<string | null> = this.highlightedSentenceIdSubject.asObservable();

    // Track the color for sentence-specific highlighting
    private sentenceHighlightColorSubject = new BehaviorSubject<string>('#999999');
    public sentenceHighlightColor$: Observable<string> = this.sentenceHighlightColorSubject.asObservable();

    /**
     * Set which emoji is currently hovered (highlights all sentences containing this emoji)
     */
    setHoveredEmoji(emoji: string | null, color: string = '#999999'): void {
        this.hoveredEmojiSubject.next(emoji);
        this.highlightColorSubject.next(color);
        // Clear sentence-specific highlighting when character highlighting is set
        this.clearSentenceHighlight();
    }

    /**
     * Clear all highlighting
     */
    clearHover(): void {
        this.hoveredEmojiSubject.next(null);
        this.highlightColorSubject.next('#999999');
        this.clearSentenceHighlight();
    }

    /**
     * Highlight a specific sentence with a specific color (for sentiment points)
     */
    highlightSentence(sentenceId: string | null, color: string = '#999999'): void {
        this.highlightedSentenceIdSubject.next(sentenceId);
        this.sentenceHighlightColorSubject.next(color);
        // Clear character highlighting when sentence highlighting is set
        this.hoveredEmojiSubject.next(null);
        this.highlightColorSubject.next('#999999');
    }

    /**
     * Clear sentence-specific highlighting
     */
    clearSentenceHighlight(): void {
        this.highlightedSentenceIdSubject.next(null);
        this.sentenceHighlightColorSubject.next('#999999');
    }
}
