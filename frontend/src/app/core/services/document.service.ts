/**
 * Document service - manages document state and syncing with backend
 * Central state management for the current document and sentences
 */
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap, tap } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
    Document,
    DocumentDetail,
    DocumentMetadata,
    Sentence,
    SentenceUpdate,
    EmojiDictionary,
    Chapter
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
     * Transform backend response (snake_case) to frontend format (camelCase)
     */
    private transformDocumentResponse(doc: any): DocumentDetail {
        // Transform sentences
        if (doc.sentences) {
            doc.sentences.forEach((s: any) => {
                if (!s.emojis) s.emojis = [];
                // Transform emoji_mappings to emojiMappings (handle both undefined and null)
                if ('emoji_mappings' in s) {
                    s.emojiMappings = s.emoji_mappings;
                    delete s.emoji_mappings;
                }
                // Transform character_refs to characterRefs
                if ('character_refs' in s) {
                    s.characterRefs = s.character_refs;
                    delete s.character_refs;
                }
                // Transform document_id to documentId
                if ('document_id' in s) {
                    s.documentId = s.document_id;
                    delete s.document_id;
                }
                // Transform chapter_id to chapterId
                if ('chapter_id' in s) {
                    s.chapterId = s.chapter_id;
                    delete s.chapter_id;
                }
            });
        }
        // Transform characters
        if (doc.characters) {
            doc.characters.forEach((c: any) => {
                if ('document_id' in c) {
                    c.documentId = c.document_id;
                    delete c.document_id;
                }
                if ('word_phrases' in c) {
                    c.wordPhrases = c.word_phrases;
                    delete c.word_phrases;
                }
                if ('created_at' in c) {
                    c.createdAt = c.created_at;
                    delete c.created_at;
                }
            });
        }
        // Transform chapters
        if (doc.chapters) {
            doc.chapters.forEach((ch: any) => {
                if ('document_id' in ch) {
                    ch.documentId = ch.document_id;
                    delete ch.document_id;
                }
                // Ensure type and emoji are set (default to 'chapter' if not present)
                if (!ch.type) ch.type = 'chapter';
                if (!ch.emoji) ch.emoji = null;
                if ('created_at' in ch) {
                    ch.createdAt = ch.created_at;
                    delete ch.created_at;
                }
                if ('updated_at' in ch) {
                    ch.updatedAt = ch.updated_at;
                    delete ch.updated_at;
                }
            });
        }
        // Transform document fields
        if ('created_at' in doc) {
            doc.createdAt = doc.created_at;
            delete doc.created_at;
        }
        if ('updated_at' in doc) {
            doc.updatedAt = doc.updated_at;
            delete doc.updated_at;
        }
        return doc as DocumentDetail;
    }

    /**
     * Create a new document from text
     */
    createDocument(title: string, content: string): Observable<DocumentDetail> {
        return this.apiService.post<any>('/api/documents/', { title, content })
            .pipe(
                tap((doc: any) => {
                    const transformed = this.transformDocumentResponse(doc);
                    this.currentDocumentSubject.next(transformed);
                })
            );
    }

    /**
     * Upload and create document from PDF file
     */
    uploadPdfDocument(formData: FormData): Observable<DocumentDetail> {
        return this.apiService.post<any>('/api/documents/upload-pdf', formData)
            .pipe(
                tap((doc: any) => {
                    const transformed = this.transformDocumentResponse(doc);
                    this.currentDocumentSubject.next(transformed);
                })
            );
    }

    /**
     * Load a document by ID
     */
    loadDocument(id: string): Observable<DocumentDetail> {
        return this.apiService.get<any>(`/api/documents/${id}`)
            .pipe(
                tap((doc: any) => {
                    const transformed = this.transformDocumentResponse(doc);
                    this.currentDocumentSubject.next(transformed);
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
     * Uses the provided content directly (backend will preserve chapter assignments)
     */
    updateDocumentContent(documentId: string, content: string): void {
        this.apiService.patch<any>(`/api/documents/${documentId}`, { content })
            .subscribe({
                next: (updatedDoc: any) => {
                    const transformed = this.transformDocumentResponse(updatedDoc);
                    this.currentDocumentSubject.next(transformed);
                    // Clear sentence selection since sentences have been re-parsed
                    this.selectedSentenceSubject.next(null);
                },
                error: (err) => console.error('Error updating document content:', err)
            });
    }

    /**
     * Update a specific chapter's content (preserves other chapters)
     */
    updateChapterContent(documentId: string, chapterId: string, chapterContent: string): void {
        const currentDoc = this.currentDocumentSubject.value;
        if (!currentDoc) return;
        
        // Get all chapters in order
        const chapters = [...(currentDoc.chapters || [])].sort((a, b) => a.index - b.index);
        
        // Reconstruct full document content by combining all chapters
        const allChapterContents: string[] = [];
        
        for (const chapter of chapters) {
            if (chapter.id === chapterId) {
                // Use the new content for the updated chapter
                allChapterContents.push(chapterContent);
            } else {
                // Preserve other chapters' content
                const chapterSentences = currentDoc.sentences
                    .filter(s => s.chapterId === chapter.id)
                    .sort((a, b) => a.index - b.index)
                    .map(s => s.text);
                allChapterContents.push(chapterSentences.join(' ').trim());
            }
        }
        
        // Add unassigned sentences
        const unassignedSentences = currentDoc.sentences
            .filter(s => !s.chapterId)
            .sort((a, b) => a.index - b.index)
            .map(s => s.text);
        if (unassignedSentences.length > 0) {
            allChapterContents.push(unassignedSentences.join(' ').trim());
        }
        
        // Combine all chapters
        const fullContent = allChapterContents.filter(c => c).join(' ').trim();
        
        // Update document with reconstructed content
        this.updateDocumentContent(documentId, fullContent);
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

    /**
     * Merge two emojis - replace all occurrences of sourceEmoji with targetEmoji
     */
    mergeEmojis(documentId: string, sourceEmoji: string, targetEmoji: string): Observable<any> {
        return this.apiService.post(`/api/documents/${documentId}/merge-emojis`, {
            source_emoji: sourceEmoji,
            target_emoji: targetEmoji
        });
    }

    /**
     * Create a new character
     */
    createCharacter(documentId: string, character: { name: string; emoji: string; description: string; color: string }): Observable<any> {
        return this.apiService.post(`/api/documents/${documentId}/characters`, character);
    }

    /**
     * Update an existing character
     */
    updateCharacter(documentId: string, characterId: string, updates: { name?: string; description?: string; color?: string; emoji?: string }): Observable<any> {
        return this.apiService.patch(`/api/documents/${documentId}/characters/${characterId}`, updates);
    }

    /**
     * Normalize character: convert raw emoji usage to character references
     */
    normalizeCharacter(documentId: string, characterId: string): Observable<any> {
        return this.apiService.post(`/api/documents/${documentId}/characters/${characterId}/normalize`, {});
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

    /**
     * Create a new chapter
     */
    createChapter(documentId: string, title?: string, type?: string, emoji?: string): Observable<Chapter> {
        return this.apiService.post<any>(`/api/documents/${documentId}/chapters/`, { 
            title, 
            type: type || 'chapter',
            emoji 
        })
            .pipe(
                switchMap((chapterResponse: any) => {
                    // Transform chapter response (snake_case to camelCase)
                    const chapter: Chapter = {
                        id: chapterResponse.id,
                        documentId: chapterResponse.document_id || chapterResponse.documentId,
                        title: chapterResponse.title,
                        type: chapterResponse.type || 'chapter',
                        emoji: chapterResponse.emoji || null,
                        index: chapterResponse.index,
                        createdAt: chapterResponse.created_at || chapterResponse.createdAt,
                        updatedAt: chapterResponse.updated_at || chapterResponse.updatedAt
                    };
                    
                    // Reload document to get updated chapters and sentences, then return the chapter
                    return this.loadDocument(documentId).pipe(
                        map((): Chapter => chapter)
                    );
                })
            );
    }

    /**
     * Update a chapter
     */
    updateChapter(documentId: string, chapterId: string, title?: string, type?: string, emoji?: string): Observable<Chapter> {
        const updateData: any = {};
        if (title !== undefined) updateData.title = title;
        if (type !== undefined) updateData.type = type;
        if (emoji !== undefined) updateData.emoji = emoji;
        
        return this.apiService.patch<Chapter>(`/api/documents/${documentId}/chapters/${chapterId}`, updateData)
            .pipe(
                switchMap(() => {
                    // Reload document to get updated chapters (including renumbered ones)
                    return this.loadDocument(documentId).pipe(
                        map(() => {
                            // Return the updated chapter from the reloaded document
                            const doc = this.currentDocumentSubject.value;
                            return doc?.chapters.find(ch => ch.id === chapterId) || {} as Chapter;
                        })
                    );
                })
            );
    }

    /**
     * Delete a chapter
     */
    deleteChapter(documentId: string, chapterId: string): Observable<void> {
        return this.apiService.delete<void>(`/api/documents/${documentId}/chapters/${chapterId}`)
            .pipe(
                tap(() => {
                    // Reload document to get updated chapters
                    this.loadDocument(documentId).subscribe();
                })
            );
    }

    /**
     * Reorder chapters
     */
    reorderChapters(documentId: string, chapterOrder: string[]): Observable<void> {
        return this.apiService.post<void>(`/api/documents/${documentId}/chapters/reorder`, { chapter_order: chapterOrder })
            .pipe(
                tap(() => {
                    // Reload document to get updated chapters
                    this.loadDocument(documentId).subscribe();
                })
            );
    }

    /**
     * Get all chapters for a document
     */
    getChapters(documentId: string): Observable<Chapter[]> {
        return this.apiService.get<Chapter[]>(`/api/documents/${documentId}/chapters/`);
    }
}
