/**
 * Chapter State Service - Manages isolated state per chapter
 *
 * Each chapter maintains:
 * - Cursor position
 * - Selection range
 * - Undo/redo history
 * - Active editing state
 *
 * This ensures complete isolation between chapters.
 */
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface CursorState {
  chapterId: string;
  sentenceId: string | null;
  offset: number; // Character offset within sentence
  timestamp: number;
}

export interface SelectionState {
  chapterId: string;
  startSentenceId: string | null;
  startOffset: number;
  endSentenceId: string | null;
  endOffset: number;
  timestamp: number;
}

export interface ChapterHistoryEntry {
  chapterId: string;
  content: string; // Full chapter content at this point
  timestamp: number;
}

export interface ChapterState {
  chapterId: string;
  cursor: CursorState | null;
  selection: SelectionState | null;
  history: ChapterHistoryEntry[];
  historyIndex: number; // Current position in history
  isActive: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ChapterStateService {
  // Map of chapterId -> ChapterState
  private chapterStates = new Map<string, ChapterState>();

  // Currently active chapter (the one being edited)
  private activeChapterIdSubject = new BehaviorSubject<string | null>(null);
  public activeChapterId$: Observable<string | null> = this.activeChapterIdSubject.asObservable();

  constructor() {}

  /**
   * Get or create state for a chapter
   */
  private getOrCreateChapterState(chapterId: string): ChapterState {
    if (!this.chapterStates.has(chapterId)) {
      this.chapterStates.set(chapterId, {
        chapterId,
        cursor: null,
        selection: null,
        history: [],
        historyIndex: -1,
        isActive: false
      });
    }
    return this.chapterStates.get(chapterId)!;
  }

  /**
   * Set the active chapter (the one currently being edited)
   */
  setActiveChapter(chapterId: string | null): void {
    const previousActive = this.activeChapterIdSubject.value;

    // Prevent redundant updates that cause cursor jumping
    if (previousActive === chapterId) {
      return;
    }

    // Deactivate previous chapter
    if (previousActive) {
      const prevState = this.chapterStates.get(previousActive);
      if (prevState) {
        prevState.isActive = false;
      }
    }

    // Activate new chapter
    this.activeChapterIdSubject.next(chapterId);
    if (chapterId) {
      const state = this.getOrCreateChapterState(chapterId);
      state.isActive = true;
    }
  }

  /**
   * Get the currently active chapter ID
   */
  getActiveChapterId(): string | null {
    return this.activeChapterIdSubject.value;
  }

  /**
   * Save cursor position for a chapter
   */
  saveCursor(chapterId: string, sentenceId: string | null, offset: number): void {
    const state = this.getOrCreateChapterState(chapterId);
    state.cursor = {
      chapterId,
      sentenceId,
      offset,
      timestamp: Date.now()
    };
  }

  /**
   * Get cursor position for a chapter
   */
  getCursor(chapterId: string): CursorState | null {
    const state = this.chapterStates.get(chapterId);
    return state?.cursor || null;
  }

  /**
   * Save selection range for a chapter
   */
  saveSelection(
    chapterId: string,
    startSentenceId: string | null,
    startOffset: number,
    endSentenceId: string | null,
    endOffset: number
  ): void {
    const state = this.getOrCreateChapterState(chapterId);
    state.selection = {
      chapterId,
      startSentenceId,
      startOffset,
      endSentenceId,
      endOffset,
      timestamp: Date.now()
    };
  }

  /**
   * Get selection range for a chapter
   */
  getSelection(chapterId: string): SelectionState | null {
    const state = this.chapterStates.get(chapterId);
    return state?.selection || null;
  }

  /**
   * Clear selection for a chapter
   */
  clearSelection(chapterId: string): void {
    const state = this.chapterStates.get(chapterId);
    if (state) {
      state.selection = null;
    }
  }

  /**
   * Add entry to chapter's undo/redo history
   */
  addHistoryEntry(chapterId: string, content: string): void {
    const state = this.getOrCreateChapterState(chapterId);

    // Remove any history entries after current index (when user makes new edit after undo)
    if (state.historyIndex < state.history.length - 1) {
      state.history = state.history.slice(0, state.historyIndex + 1);
    }

    // Add new entry
    state.history.push({
      chapterId,
      content,
      timestamp: Date.now()
    });

    // Limit history size (keep last 50 entries)
    if (state.history.length > 50) {
      state.history = state.history.slice(-50);
    }

    state.historyIndex = state.history.length - 1;
  }

  /**
   * Get undo state for a chapter
   */
  canUndo(chapterId: string): boolean {
    const state = this.chapterStates.get(chapterId);
    return state ? state.historyIndex > 0 : false;
  }

  /**
   * Get redo state for a chapter
   */
  canRedo(chapterId: string): boolean {
    const state = this.chapterStates.get(chapterId);
    return state ? state.historyIndex < state.history.length - 1 : false;
  }

  /**
   * Undo for a chapter - returns previous content state
   */
  undo(chapterId: string): string | null {
    const state = this.chapterStates.get(chapterId);
    if (!state || state.historyIndex <= 0) {
      return null;
    }

    state.historyIndex--;
    return state.history[state.historyIndex].content;
  }

  /**
   * Redo for a chapter - returns next content state
   */
  redo(chapterId: string): string | null {
    const state = this.chapterStates.get(chapterId);
    if (!state || state.historyIndex >= state.history.length - 1) {
      return null;
    }

    state.historyIndex++;
    return state.history[state.historyIndex].content;
  }

  /**
   * Get current content from history for a chapter
   */
  getCurrentContent(chapterId: string): string | null {
    const state = this.chapterStates.get(chapterId);
    if (!state || state.historyIndex < 0 || state.historyIndex >= state.history.length) {
      return null;
    }
    return state.history[state.historyIndex].content;
  }

  /**
   * Initialize history for a chapter with initial content
   */
  initializeHistory(chapterId: string, initialContent: string): void {
    const state = this.getOrCreateChapterState(chapterId);
    if (state.history.length === 0) {
      state.history.push({
        chapterId,
        content: initialContent,
        timestamp: Date.now()
      });
      state.historyIndex = 0;
    }
  }

  /**
   * Sync history with external content change
   * If content is different from current history tip, add a new entry.
   * This is used when the document is updated from sources other than direct typing
   * (e.g. AI suggestions, backend normalization).
   */
  syncHistory(chapterId: string, content: string): void {
    const state = this.getOrCreateChapterState(chapterId);

    // If no history, initialize it
    if (state.history.length === 0) {
      this.initializeHistory(chapterId, content);
      return;
    }

    // Check if content matches current history tip
    const currentHist = this.getCurrentContent(chapterId);
    if (currentHist !== content) {
      this.addHistoryEntry(chapterId, content);
    }
  }

  /**
   * Remove state for a deleted chapter
   */
  removeChapterState(chapterId: string): void {
    this.chapterStates.delete(chapterId);
    if (this.activeChapterIdSubject.value === chapterId) {
      this.activeChapterIdSubject.next(null);
    }
  }

  /**
   * Get all chapter states (for debugging)
   */
  getAllStates(): Map<string, ChapterState> {
    return new Map(this.chapterStates);
  }

  /**
   * Get active chapter's content from document service
   * This is a helper method that requires document service to be passed
   * or called from a component that has access to document service
   */
  getActiveChapterContent(doc: any): string {
    const activeChapterId = this.getActiveChapterId();
    if (!activeChapterId || !doc || !doc.sentences) {
      return '';
    }
    const activeChapterSentences = doc.sentences
      .filter((s: any) => s.chapterId === activeChapterId)
      .sort((a: any, b: any) => a.index - b.index)
      .map((s: any) => s.text);
    return activeChapterSentences.join(' ').trim();
  }
}
