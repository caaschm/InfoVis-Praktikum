/**
 * Service for managing enhanced emoji features:
 * - Word-level emoji mappings
 * - Custom emoji sets
 * - Character definitions
 */
import { Injectable } from '@angular/core';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
    WordEmojiMapping,
    WordEmojiMappingCreate,
    WordEmojiMappingUpdate,
    CustomEmojiSet,
    CustomEmojiSetCreate,
    CustomEmojiSetUpdate,
    CharacterDefinition,
    CharacterDefinitionCreate,
    CharacterDefinitionUpdate
} from '../models/document.model';

@Injectable({
    providedIn: 'root'
})
export class EmojiMappingService {
    // State management
    private wordMappingsSubject = new BehaviorSubject<WordEmojiMapping[]>([]);
    public wordMappings$ = this.wordMappingsSubject.asObservable();

    private customSetsSubject = new BehaviorSubject<CustomEmojiSet[]>([]);
    public customSets$ = this.customSetsSubject.asObservable();

    private charactersSubject = new BehaviorSubject<CharacterDefinition[]>([]);
    public characters$ = this.charactersSubject.asObservable();

    constructor(private api: ApiService) { }

    // ========== Word Emoji Mappings ==========

    loadWordMappings(documentId: string): Observable<WordEmojiMapping[]> {
        return this.api.get<WordEmojiMapping[]>(`/api/documents/${documentId}/emoji-mappings/words`)
            .pipe(tap(mappings => this.wordMappingsSubject.next(mappings)));
    }

    createWordMapping(documentId: string, mapping: WordEmojiMappingCreate): Observable<WordEmojiMapping> {
        return this.api.post<WordEmojiMapping>(`/api/documents/${documentId}/emoji-mappings/words`, mapping)
            .pipe(tap(newMapping => {
                const current = this.wordMappingsSubject.value;
                this.wordMappingsSubject.next([...current, newMapping]);
            }));
    }

    updateWordMapping(documentId: string, mappingId: string, update: WordEmojiMappingUpdate): Observable<WordEmojiMapping> {
        return this.api.patch<WordEmojiMapping>(`/api/documents/${documentId}/emoji-mappings/words/${mappingId}`, update)
            .pipe(tap(updatedMapping => {
                const current = this.wordMappingsSubject.value;
                const index = current.findIndex(m => m.id === mappingId);
                if (index !== -1) {
                    current[index] = updatedMapping;
                    this.wordMappingsSubject.next([...current]);
                }
            }));
    }

    deleteWordMapping(documentId: string, mappingId: string): Observable<void> {
        return this.api.delete<void>(`/api/documents/${documentId}/emoji-mappings/words/${mappingId}`)
            .pipe(tap(() => {
                const current = this.wordMappingsSubject.value;
                this.wordMappingsSubject.next(current.filter(m => m.id !== mappingId));
            }));
    }

    // ========== Custom Emoji Sets ==========

    loadCustomSets(documentId: string): Observable<CustomEmojiSet[]> {
        return this.api.get<CustomEmojiSet[]>(`/api/documents/${documentId}/emoji-mappings/sets`)
            .pipe(tap(sets => this.customSetsSubject.next(sets)));
    }

    createCustomSet(documentId: string, set: CustomEmojiSetCreate): Observable<CustomEmojiSet> {
        return this.api.post<CustomEmojiSet>(`/api/documents/${documentId}/emoji-mappings/sets`, set)
            .pipe(tap(newSet => {
                const current = this.customSetsSubject.value;
                this.customSetsSubject.next([...current, newSet]);
            }));
    }

    updateCustomSet(documentId: string, setId: string, update: CustomEmojiSetUpdate): Observable<CustomEmojiSet> {
        return this.api.patch<CustomEmojiSet>(`/api/documents/${documentId}/emoji-mappings/sets/${setId}`, update)
            .pipe(tap(updatedSet => {
                const current = this.customSetsSubject.value;
                const index = current.findIndex(s => s.id === setId);
                if (index !== -1) {
                    current[index] = updatedSet;
                    this.customSetsSubject.next([...current]);
                }
            }));
    }

    deleteCustomSet(documentId: string, setId: string): Observable<void> {
        return this.api.delete<void>(`/api/documents/${documentId}/emoji-mappings/sets/${setId}`)
            .pipe(tap(() => {
                const current = this.customSetsSubject.value;
                this.customSetsSubject.next(current.filter(s => s.id !== setId));
            }));
    }

    // ========== Character Definitions ==========

    loadCharacters(documentId: string): Observable<CharacterDefinition[]> {
        return this.api.get<CharacterDefinition[]>(`/api/documents/${documentId}/emoji-mappings/characters`)
            .pipe(tap(chars => this.charactersSubject.next(chars)));
    }

    createCharacter(documentId: string, character: CharacterDefinitionCreate): Observable<CharacterDefinition> {
        return this.api.post<CharacterDefinition>(`/api/documents/${documentId}/emoji-mappings/characters`, character)
            .pipe(tap(newChar => {
                const current = this.charactersSubject.value;
                this.charactersSubject.next([...current, newChar]);
            }));
    }

    updateCharacter(documentId: string, characterId: string, update: CharacterDefinitionUpdate): Observable<CharacterDefinition> {
        return this.api.patch<CharacterDefinition>(`/api/documents/${documentId}/emoji-mappings/characters/${characterId}`, update)
            .pipe(tap(updatedChar => {
                const current = this.charactersSubject.value;
                const index = current.findIndex(c => c.id === characterId);
                if (index !== -1) {
                    current[index] = updatedChar;
                    this.charactersSubject.next([...current]);
                }
            }));
    }

    deleteCharacter(documentId: string, characterId: string): Observable<void> {
        return this.api.delete<void>(`/api/documents/${documentId}/emoji-mappings/characters/${characterId}`)
            .pipe(tap(() => {
                const current = this.charactersSubject.value;
                this.charactersSubject.next(current.filter(c => c.id !== characterId));
            }));
    }

    // ========== Utility Methods ==========

    /**
     * Get emoji for a specific word based on active mappings
     */
    getEmojiForWord(word: string): string | null {
        const mappings = this.wordMappingsSubject.value;
        const activeMapping = mappings.find(m =>
            m.isActive && m.wordPattern.toLowerCase() === word.toLowerCase()
        );
        return activeMapping ? activeMapping.emoji : null;
    }

    /**
     * Get all characters that match a given word
     */
    getCharactersForWord(word: string): CharacterDefinition[] {
        const characters = this.charactersSubject.value;
        return characters.filter(char =>
            char.name.toLowerCase() === word.toLowerCase() ||
            char.aliases.some(alias => alias.toLowerCase() === word.toLowerCase())
        );
    }

    /**
     * Get the default custom emoji set
     */
    getDefaultEmojiSet(): CustomEmojiSet | null {
        const sets = this.customSetsSubject.value;
        return sets.find(s => s.isDefault) || null;
    }

    /**
     * Clear all cached data
     */
    clearCache(): void {
        this.wordMappingsSubject.next([]);
        this.customSetsSubject.next([]);
        this.charactersSubject.next([]);
    }
}
