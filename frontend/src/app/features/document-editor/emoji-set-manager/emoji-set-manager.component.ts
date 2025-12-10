import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { EmojiMappingService } from '../../../core/services/emoji-mapping.service';
import { CustomEmojiSet, DocumentDetail } from '../../../core/models/document.model';

@Component({
    selector: 'app-emoji-set-manager',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './emoji-set-manager.component.html',
    styleUrl: './emoji-set-manager.component.scss'
})
export class EmojiSetManagerComponent implements OnInit, OnDestroy {
    currentDocument: DocumentDetail | null = null;
    emojiSets: CustomEmojiSet[] = [];

    // Form state
    showAddForm = false;
    newName = '';
    selectedEmojis: string[] = [];
    setAsDefault = false;

    // Emoji categories for selection
    emojiCategories = {
        'Emotions': ['😀', '😊', '😢', '😱', '😡', '😍', '🤔', '😴', '😂', '😭', '😰', '😈'],
        'Fantasy': ['🧙‍♂️', '🧚', '🧛', '🧜‍♂️', '🐉', '🦄', '👑', '🗡️', '🛡️', '🏰', '🪄', '📜'],
        'Nature': ['🌙', '☀️', '⛈️', '🌈', '🔥', '💧', '🌟', '✨', '🌸', '🌺', '🍃', '🌊'],
        'Objects': ['📖', '🎨', '🎭', '🎪', '🎬', '🎵', '🎉', '💎', '🗝️', '🔮', '⏰', '💌'],
        'Animals': ['🦊', '🐺', '🦅', '🦉', '🐍', '🐢', '🦋', '🐝', '🐉', '🦁', '🐯', '🐻']
    };

    activeCategory: keyof typeof this.emojiCategories = 'Emotions';

    private destroy$ = new Subject<void>();

    constructor(
        private documentService: DocumentService,
        private emojiMappingService: EmojiMappingService
    ) { }

    ngOnInit(): void {
        this.documentService.currentDocument$
            .pipe(takeUntil(this.destroy$))
            .subscribe(doc => this.currentDocument = doc);

        this.emojiMappingService.customSets$
            .pipe(takeUntil(this.destroy$))
            .subscribe(sets => this.emojiSets = sets);
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

    selectCategory(category: keyof typeof this.emojiCategories): void {
        this.activeCategory = category;
    }

    toggleEmoji(emoji: string): void {
        const index = this.selectedEmojis.indexOf(emoji);
        if (index > -1) {
            this.selectedEmojis.splice(index, 1);
        } else {
            this.selectedEmojis.push(emoji);
        }
    }

    isEmojiSelected(emoji: string): boolean {
        return this.selectedEmojis.includes(emoji);
    }

    addEmojiSet(): void {
        if (!this.currentDocument || !this.newName.trim() || this.selectedEmojis.length === 0) {
            return;
        }

        this.emojiMappingService.createCustomSet(this.currentDocument.id, {
            name: this.newName.trim(),
            emojis: this.selectedEmojis,
            isDefault: this.setAsDefault
        }).subscribe({
            next: () => {
                this.resetForm();
                this.showAddForm = false;
            },
            error: (err) => console.error('Error creating emoji set:', err)
        });
    }

    setAsDefaultSet(set: CustomEmojiSet): void {
        if (!this.currentDocument) return;

        this.emojiMappingService.updateCustomSet(
            this.currentDocument.id,
            set.id,
            { isDefault: true }
        ).subscribe({
            error: (err) => console.error('Error updating emoji set:', err)
        });
    }

    deleteEmojiSet(set: CustomEmojiSet): void {
        if (!this.currentDocument) return;

        if (confirm(`Delete emoji set "${set.name}"?`)) {
            this.emojiMappingService.deleteCustomSet(
                this.currentDocument.id,
                set.id
            ).subscribe({
                error: (err) => console.error('Error deleting emoji set:', err)
            });
        }
    }

    private resetForm(): void {
        this.newName = '';
        this.selectedEmojis = [];
        this.setAsDefault = false;
        this.activeCategory = 'Emotions';
    }

    getCategoryKeys(): (keyof typeof this.emojiCategories)[] {
        return Object.keys(this.emojiCategories) as (keyof typeof this.emojiCategories)[];
    }
}
