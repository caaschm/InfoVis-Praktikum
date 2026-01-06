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

    /**
     * Set which emoji is currently hovered (highlights all sentences containing this emoji)
     */
    setHoveredEmoji(emoji: string | null, color: string = '#999999'): void {
        this.hoveredEmojiSubject.next(emoji);
        this.highlightColorSubject.next(color);
    }

    /**
     * Clear all highlighting
     */
    clearHover(): void {
        this.hoveredEmojiSubject.next(null);
        this.highlightColorSubject.next('#999999');
    }
}
