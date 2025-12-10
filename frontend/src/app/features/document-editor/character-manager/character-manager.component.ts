import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { EmojiMappingService } from '../../../core/services/emoji-mapping.service';
import { CharacterDefinition, DocumentDetail } from '../../../core/models/document.model';

@Component({
    selector: 'app-character-manager',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './character-manager.component.html',
    styleUrl: './character-manager.component.scss'
})
export class CharacterManagerComponent implements OnInit, OnDestroy {
    currentDocument: DocumentDetail | null = null;
    characters: CharacterDefinition[] = [];

    // Form state
    showAddForm = false;
    newName = '';
    newEmoji = '';
    newAliases = '';
    newDescription = '';
    newColor = '#FF5733';

    // Predefined colors for quick selection
    predefinedColors = [
        '#FF5733', '#33FF57', '#3357FF', '#F333FF', '#FF33F3',
        '#33FFF3', '#FFD700', '#FF6347', '#4B0082', '#00CED1'
    ];

    // Common emojis for character types
    characterEmojis = [
        '👑', '🧙‍♂️', '🧙‍♀️', '🧛‍♂️', '🧛‍♀️', '🧜‍♂️', '🧜‍♀️', '🧚‍♂️',
        '🧚‍♀️', '🧝‍♂️', '🧝‍♀️', '🧞', '🧟', '🦸‍♂️', '🦸‍♀️', '🦹‍♂️',
        '🦹‍♀️', '👸', '🤴', '👮', '🕵️', '💂', '🥷', '👷',
        '🤠', '🧑‍🚀', '🧑‍🔬', '🧑‍⚕️', '🧑‍🎓', '🧑‍🏫', '🧑‍⚖️', '🧑‍🌾'
    ];

    private destroy$ = new Subject<void>();

    constructor(
        private documentService: DocumentService,
        private emojiMappingService: EmojiMappingService
    ) { }

    ngOnInit(): void {
        this.documentService.currentDocument$
            .pipe(takeUntil(this.destroy$))
            .subscribe(doc => this.currentDocument = doc);

        this.emojiMappingService.characters$
            .pipe(takeUntil(this.destroy$))
            .subscribe(chars => this.characters = chars);
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

    selectColor(color: string): void {
        this.newColor = color;
    }

    addCharacter(): void {
        if (!this.currentDocument || !this.newName.trim() || !this.newEmoji) {
            return;
        }

        const aliases = this.newAliases
            .split(',')
            .map(a => a.trim())
            .filter(a => a.length > 0);

        this.emojiMappingService.createCharacter(this.currentDocument.id, {
            name: this.newName.trim(),
            emoji: this.newEmoji,
            aliases: aliases,
            description: this.newDescription.trim() || undefined,
            color: this.newColor
        }).subscribe({
            next: () => {
                this.resetForm();
                this.showAddForm = false;
            },
            error: (err) => console.error('Error creating character:', err)
        });
    }

    deleteCharacter(character: CharacterDefinition): void {
        if (!this.currentDocument) return;

        if (confirm(`Delete character "${character.name}"?`)) {
            this.emojiMappingService.deleteCharacter(
                this.currentDocument.id,
                character.id
            ).subscribe({
                error: (err) => console.error('Error deleting character:', err)
            });
        }
    }

    private resetForm(): void {
        this.newName = '';
        this.newEmoji = '';
        this.newAliases = '';
        this.newDescription = '';
        this.newColor = '#FF5733';
    }
}
