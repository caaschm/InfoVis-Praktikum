import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { ApiService } from '../../../core/services/api.service';
import { Character, DocumentDetail, CharacterCreate } from '../../../core/models/document.model';

@Component({
    selector: 'app-character-manager',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './character-manager.component.html',
    styleUrl: './character-manager.component.scss'
})
export class CharacterManagerComponent implements OnInit, OnDestroy {
    currentDocument: DocumentDetail | null = null;
    characters: Character[] = [];

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
        private apiService: ApiService
    ) { }

    ngOnInit(): void {
        this.documentService.currentDocument$
            .pipe(takeUntil(this.destroy$))
            .subscribe(doc => {
                this.currentDocument = doc;
                this.characters = doc?.characters || [];
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

    selectColor(color: string): void {
        this.newColor = color;
    }

    addCharacter(): void {
        if (!this.currentDocument || !this.newName.trim() || !this.newEmoji) {
            return;
        }

        const documentId = this.currentDocument.id; // Store ID to avoid null issues in callbacks

        const aliases = this.newAliases
            .split(',')
            .map(a => a.trim())
            .filter(a => a.length > 0);

        const characterData: CharacterCreate = {
            name: this.newName.trim(),
            emoji: this.newEmoji,
            color: this.newColor,
            aliases: aliases,
            description: this.newDescription.trim() || undefined
        };

        this.apiService.post<Character>(
            `/api/documents/${documentId}/characters`,
            characterData
        ).subscribe({
            next: (newCharacter) => {
                // Selectively normalize sentences mentioning this character (non-destructive)
                this.apiService.post(
                    `/api/documents/${documentId}/characters/${newCharacter.id}/normalize`,
                    {}
                ).subscribe({
                    next: (result: any) => {
                        console.log(`✅ ${result.message}`);
                        this.resetForm();
                        this.showAddForm = false;
                        // Reload document to get updated characters and sentences
                        this.documentService.loadDocument(documentId).subscribe();
                    },
                    error: (err) => console.error('Error normalizing character:', err)
                });
            },
            error: (err) => console.error('Error creating character:', err)
        });
    }

    deleteCharacter(character: Character): void {
        if (!this.currentDocument) return;

        if (confirm(`Delete character "${character.name}"?`)) {
            this.apiService.delete(
                `/api/documents/${this.currentDocument.id}/characters/${character.id}`
            ).subscribe({
                next: () => {
                    // Reload document to get updated characters
                    this.documentService.loadDocument(this.currentDocument!.id).subscribe();
                },
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
