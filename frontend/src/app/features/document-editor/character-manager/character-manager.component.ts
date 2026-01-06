import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { ApiService } from '../../../core/services/api.service';
import { CharacterHighlightService } from '../../../core/services/character-highlight.service';
import { CharacterFormService } from '../../../core/services/character-form.service';
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

    // Word phrases editing state
    editingPhrasesId: string | null = null;
    editablePhrasesMap: Map<string, string[]> = new Map();

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
        private apiService: ApiService,
        private characterHighlightService: CharacterHighlightService,
        private characterFormService: CharacterFormService
    ) { }

    ngOnInit(): void {
        this.documentService.currentDocument$
            .pipe(takeUntil(this.destroy$))
            .subscribe(doc => {
                this.currentDocument = doc;
                this.characters = doc?.characters || [];
            });

        // Listen for form open requests (e.g., from emoji dictionary promote button)
        this.characterFormService.openForm$
            .pipe(takeUntil(this.destroy$))
            .subscribe(formData => {
                if (formData) {
                    // Pre-fill form with data from emoji dictionary
                    this.showAddForm = true;
                    this.newEmoji = formData.emoji;
                    this.newName = formData.suggestedName || '';
                    this.newDescription = formData.description || '';
                    // Clear the request after handling
                    this.characterFormService.clearFormRequest();
                }
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

    resetForm(): void {
        this.newName = '';
        this.newEmoji = '';
        this.newAliases = '';
        this.newDescription = '';
        this.newColor = '#FF5733';
    }

    onCharacterHover(characterId: string): void {
        const character = this.characters.find(c => c.id === characterId);
        if (character) {
            this.characterHighlightService.setHoveredEmoji(character.emoji, character.color);
        }
    }

    onCharacterLeave(): void {
        this.characterHighlightService.clearHover();
    }

    // Word phrases editing methods
    toggleEditPhrases(characterId: string): void {
        if (this.editingPhrasesId === characterId) {
            // Save the changes
            this.savePhrases(characterId);
        } else {
            // Enter edit mode
            const character = this.characters.find(c => c.id === characterId);
            if (character) {
                // Create a copy of the phrases for editing
                this.editablePhrasesMap.set(characterId, [...(character.wordPhrases || [])]);
                this.editingPhrasesId = characterId;
            }
        }
    }

    getEditablePhrases(characterId: string): string[] {
        return this.editablePhrasesMap.get(characterId) || [];
    }

    addNewPhrase(characterId: string): void {
        const phrases = this.editablePhrasesMap.get(characterId) || [];
        phrases.push('');
        this.editablePhrasesMap.set(characterId, phrases);
    }

    removePhrase(characterId: string, index: number): void {
        const phrases = this.editablePhrasesMap.get(characterId) || [];
        phrases.splice(index, 1);
        this.editablePhrasesMap.set(characterId, phrases);
    }

    savePhrases(characterId: string): void {
        if (!this.currentDocument) return;

        const phrases = this.editablePhrasesMap.get(characterId) || [];
        // Filter out empty phrases
        const cleanedPhrases = phrases.filter(p => p.trim().length > 0);

        this.apiService.patch<Character>(
            `/api/documents/${this.currentDocument.id}/characters/${characterId}`,
            { word_phrases: cleanedPhrases }
        ).subscribe({
            next: () => {
                // Reload document to get updated character
                this.documentService.loadDocument(this.currentDocument!.id).subscribe({
                    next: () => {
                        this.editingPhrasesId = null;
                        this.editablePhrasesMap.delete(characterId);
                    }
                });
            },
            error: (err) => {
                console.error('Error updating word phrases:', err);
                alert('Failed to update word associations');
            }
        });
    }
}
