import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { EmojiMappingService } from '../../../core/services/emoji-mapping.service';
import { WordEmojiMapping, DocumentDetail } from '../../../core/models/document.model';

@Component({
    selector: 'app-word-mapping-manager',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './word-mapping-manager.component.html',
    styleUrl: './word-mapping-manager.component.scss'
})
export class WordMappingManagerComponent implements OnInit, OnDestroy {
    currentDocument: DocumentDetail | null = null;
    wordMappings: WordEmojiMapping[] = [];

    // Form state
    showAddForm = false;
    newWordPattern = '';
    newEmoji = '';

    // Common emojis for quick selection
    commonEmojis = [
        '😀', '😊', '😢', '😱', '😡', '😍', '🤔', '😴',
        '🎉', '🎨', '🎭', '🎪', '🎬', '📖', '✨', '🌟',
        '🌙', '☀️', '⛈️', '🌈', '🔥', '💧', '💔', '💖',
        '👑', '👻', '🦄', '🐉', '🧙‍♂️', '🧛‍♀️', '🧜‍♂️', '🏰',
        '⚔️', '🛡️', '🗡️', '🏹', '🪄', '📜', '🗝️', '💎'
    ];

    private destroy$ = new Subject<void>();

    constructor(
        private documentService: DocumentService,
        private emojiMappingService: EmojiMappingService
    ) { }

    ngOnInit(): void {
        // Subscribe to current document
        this.documentService.currentDocument$
            .pipe(takeUntil(this.destroy$))
            .subscribe(doc => {
                this.currentDocument = doc;
            });

        // Subscribe to word mappings
        this.emojiMappingService.wordMappings$
            .pipe(takeUntil(this.destroy$))
            .subscribe(mappings => {
                this.wordMappings = mappings;
            });
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    toggleAddForm(): void {
        this.showAddForm = !this.showAddForm;
        if (!this.showAddForm) {
            this.resetForm();
        }
    }

    selectEmoji(emoji: string): void {
        this.newEmoji = emoji;
    }

    addMapping(): void {
        if (!this.currentDocument || !this.newWordPattern.trim() || !this.newEmoji) {
            return;
        }

        this.emojiMappingService.createWordMapping(this.currentDocument.id, {
            wordPattern: this.newWordPattern.trim(),
            emoji: this.newEmoji,
            isActive: true
        }).subscribe({
            next: () => {
                this.resetForm();
                this.showAddForm = false;
            },
            error: (err) => console.error('Error creating word mapping:', err)
        });
    }

    toggleMappingActive(mapping: WordEmojiMapping): void {
        if (!this.currentDocument) return;

        this.emojiMappingService.updateWordMapping(
            this.currentDocument.id,
            mapping.id,
            { isActive: !mapping.isActive }
        ).subscribe({
            error: (err) => console.error('Error updating word mapping:', err)
        });
    }

    deleteMapping(mapping: WordEmojiMapping): void {
        if (!this.currentDocument) return;

        if (confirm(`Delete mapping for "${mapping.wordPattern}"?`)) {
            this.emojiMappingService.deleteWordMapping(
                this.currentDocument.id,
                mapping.id
            ).subscribe({
                error: (err) => console.error('Error deleting word mapping:', err)
            });
        }
    }

    private resetForm(): void {
        this.newWordPattern = '';
        this.newEmoji = '';
    }

    // Extract unique words from document for suggestions
    getSuggestedWords(): string[] {
        if (!this.currentDocument) return [];

        const words = new Set<string>();
        const text = this.currentDocument.content.toLowerCase();
        const wordMatches = text.match(/\b[a-z]+\b/gi);

        if (wordMatches) {
            wordMatches.forEach(word => {
                if (word.length > 3) { // Only suggest words longer than 3 chars
                    words.add(word.toLowerCase());
                }
            });
        }

        // Remove words that already have mappings
        const mappedWords = new Set(this.wordMappings.map(m => m.wordPattern.toLowerCase()));
        return Array.from(words).filter(w => !mappedWords.has(w)).slice(0, 20);
    }
}
