/**
 * Document service - manages document state and syncing with backend
 * Central state management for the current document and sentences
 */
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap, tap } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
    Document,
    DocumentDetail,
    DocumentMetadata,
    Sentence,
    SentenceUpdate,
    EmojiDictionary
} from '../models/document.model';

@Injectable({
    providedIn: 'root'
})
export class DocumentService {
    // Current document state
    private currentDocumentSubject = new BehaviorSubject<DocumentDetail | null>(null);
    public currentDocument$: Observable<DocumentDetail | null> = this.currentDocumentSubject.asObservable();

    // Currently selected sentence
    private selectedSentenceSubject = new BehaviorSubject<Sentence | null>(null);
    public selectedSentence$: Observable<Sentence | null> = this.selectedSentenceSubject.asObservable();

    // Sentence updates for debounced saving
    private sentenceUpdateSubject = new Subject<{ id: string; update: SentenceUpdate }>();

    constructor(
        private apiService: ApiService
    ) {
        // Set up debounced sentence updates
        this.sentenceUpdateSubject
            .pipe(
                debounceTime(500), // Wait 500ms after last edit
                distinctUntilChanged((prev, curr) =>
                    prev.id === curr.id && JSON.stringify(prev.update) === JSON.stringify(curr.update)
                ),
                switchMap(({ id, update }) => this.saveSentenceUpdate(id, update))
            )
            .subscribe({
                next: (updatedSentence) => this.handleSentenceUpdated(updatedSentence),
                error: (err) => console.error('Error saving sentence:', err)
            });
    }

    /**
     * Create a new document from text
     */
    createDocument(title: string, content: string): Observable<DocumentDetail> {
        return this.apiService.post<DocumentDetail>('/api/documents/', { title, content })
            .pipe(
                tap(doc => {
                    this.currentDocumentSubject.next(doc);
                })
            );
    }

    /**
     * Upload and create document from PDF file
     */
    uploadPdfDocument(formData: FormData): Observable<DocumentDetail> {
        return this.apiService.post<DocumentDetail>('/api/documents/upload-pdf', formData)
            .pipe(
                tap(doc => this.currentDocumentSubject.next(doc))
            );
    }

    /**
     * Load a document by ID
     */
    loadDocument(id: string): Observable<DocumentDetail> {
        return this.apiService.get<DocumentDetail>(`/api/documents/${id}`)
            .pipe(
                tap(doc => {
                    // Initialize emojis array for compatibility during migration
                    doc.sentences.forEach(s => {
                        if (!s.emojis) s.emojis = [];
                    });
                    this.currentDocumentSubject.next(doc);
                })
            );
    }

    /**
     * Get list of all documents
     */
    listDocuments(): Observable<DocumentMetadata[]> {
        return this.apiService.get<DocumentMetadata[]>('/api/documents/');
    }

    /**
     * Delete a document
     */
    deleteDocument(id: string): Observable<void> {
        return this.apiService.delete<void>(`/api/documents/${id}`)
            .pipe(
                tap(() => {
                    const current = this.currentDocumentSubject.value;
                    if (current && current.id === id) {
                        this.currentDocumentSubject.next(null);
                    }
                })
            );
    }

    /**
     * Select a sentence (for editing emojis, etc.)
     */
    selectSentence(sentence: Sentence | null): void {
        this.selectedSentenceSubject.next(sentence);
    }

    /**
     * Update document content and re-parse sentences
     */
    updateDocumentContent(documentId: string, content: string): void {
        this.apiService.patch<DocumentDetail>(`/api/documents/${documentId}`, { content })
            .subscribe({
                next: (updatedDoc) => {
                    this.currentDocumentSubject.next(updatedDoc);
                    // Clear sentence selection since sentences have been re-parsed
                    this.selectedSentenceSubject.next(null);
                },
                error: (err) => console.error('Error updating document content:', err)
            });
    }

    /**
     * Update sentence text (debounced)
     */
    updateSentenceText(sentenceId: string, text: string): void {
        this.sentenceUpdateSubject.next({ id: sentenceId, update: { text } });
        this.updateLocalSentence(sentenceId, { text });
    }

    /**
     * Update sentence emojis (debounced)
     * Enforces max 5 emojis
     */
    updateSentenceEmojis(sentenceId: string, emojis: string[]): void {
        const limitedEmojis = emojis.slice(0, 5); // Enforce max 5
        this.sentenceUpdateSubject.next({ id: sentenceId, update: { text: undefined, emojis: limitedEmojis } });
        this.updateLocalSentence(sentenceId, { emojis: limitedEmojis });
    }

    /**
     * Get current document value
     */
    getCurrentDocument(): DocumentDetail | null {
        return this.currentDocumentSubject.value;
    }

    /**
     * Get currently selected sentence
     */
    getSelectedSentence(): Sentence | null {
        return this.selectedSentenceSubject.value;
    }

    /**
     * Get all sentences from current document
     */
    getCurrentSentences(): Sentence[] {
        const doc = this.currentDocumentSubject.value;
        return doc ? doc.sentences : [];
    }

    /**
     * Get emoji dictionary for current document
     */
    getEmojiDictionary(documentId: string): Observable<EmojiDictionary> {
        return this.apiService.get<EmojiDictionary>(`/api/documents/${documentId}/characters/emoji-dictionary`);
    }

    // Private helper methods

    private saveSentenceUpdate(id: string, update: SentenceUpdate): Observable<Sentence> {
        return this.apiService.patch<Sentence>(`/api/sentences/${id}`, update);
    }

    private updateLocalSentence(sentenceId: string, update: Partial<Sentence>): void {
        const doc = this.currentDocumentSubject.value;
        if (!doc) return;

        const updatedSentences = doc.sentences.map(s =>
            s.id === sentenceId ? { ...s, ...update } : s
        );

        this.currentDocumentSubject.next({
            ...doc,
            sentences: updatedSentences
        });

        // Update selected sentence if it's the one being modified
        const selected = this.selectedSentenceSubject.value;
        if (selected && selected.id === sentenceId) {
            this.selectedSentenceSubject.next({ ...selected, ...update });
        }
    }

    private handleSentenceUpdated(sentence: Sentence): void {
        // Sync with backend response
        this.updateLocalSentence(sentence.id, sentence);
    }
}
