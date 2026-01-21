import { Component, OnInit, OnDestroy, ChangeDetectorRef, ViewChild, ElementRef, AfterViewChecked, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { CharacterHighlightService } from '../../../core/services/character-highlight.service';
import { ChapterStateService } from '../../../core/services/chapter-state.service';
import { AiService } from '../../../core/services/ai.service';
import { Sentence, Character, Chapter, DocumentDetail } from '../../../core/models/document.model';

@Component({
  selector: 'app-text-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './text-viewer.component.html',
  styleUrl: './text-viewer.component.scss'
})
export class TextViewerComponent implements OnInit, OnDestroy, AfterViewChecked, AfterViewInit {
  sentences: Sentence[] = [];
  characters: Character[] = [];
  chapters: Chapter[] = [];
  currentDocument: DocumentDetail | null = null;
  selectedSentenceId: string | null = null;
  hoveredEmoji: string | null = null;
  highlightColor: string = '#999999';
  viewMode: 'text' | 'emoji' = 'text'; // Toggle between text and emoji-only view
  showAiHighlight: boolean = false; // Toggle for AI highlight mode
  selectedChapterId: string | null = null; // null means "All Chapters" (view filter)
  activeChapterId: string | null = null; // The chapter currently being edited (active editor)
  editingChapterId: string | null = null; // Chapter title being edited
  editingChapterTitle: string = '';
  private aiGeneratedSentenceIds = new Set<string>(); // Track AI-generated sentences
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;
  private cursorSaveTimer: any = null;
  private isScrolling = false; // Flag to prevent scroll event loops
  private scrollSyncFrame: number | null = null; // RAF ID for scroll sync
  lineNumbers: number[] = []; // Array of line numbers for actual text lines
  private lineNumberUpdateTimer: any = null;
  private charsSinceLastSnapshot = 0;

  // Track original AI text to allow partial highlighting
  private aiOriginalTextMap = new Map<string, string>();

  /**
   * KEY FIX:
   * Sobald ein AI-Satz vom User editiert wird, frieren wir das AI-Highlight ein
   * (nur UI), damit das Highlight NICHT "weiterwandert".
   */
  private aiHighlightFrozenForSentenceIds = new Set<string>();

  @ViewChild('lineNumbersContainer') lineNumbersContainer?: ElementRef<HTMLElement>;
  @ViewChild('textContentContainer') textContentContainer?: ElementRef<HTMLElement>;

  constructor(
    private documentService: DocumentService,
    private characterHighlightService: CharacterHighlightService,
    private chapterStateService: ChapterStateService,
    private aiService: AiService,
    private cdr: ChangeDetectorRef
  ) { }

  private navigateToChapterHandler = ((event: CustomEvent) => {
    if (event.detail && event.detail.chapterId) {
      this.selectChapter(event.detail.chapterId);
      // Scroll to the chapter in the view
      setTimeout(() => {
        const chapterSection = document.querySelector(`[data-chapter-id="${event.detail.chapterId}"]`);
        if (chapterSection) {
          chapterSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    }
  }) as EventListener;

  ngOnInit(): void {
    // Listen for chapter navigation events from ToC
    window.addEventListener('navigateToChapter', this.navigateToChapterHandler);

    // Subscribe to current document
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        if (doc) {
          this.currentDocument = doc;
          this.sentences = doc.sentences;
          this.characters = doc.characters || [];
          this.chapters = doc.chapters || [];

          // If a chapter is selected but no longer exists, reset to "All Chapters"
          if (this.selectedChapterId !== null) {
            const chapterExists = this.chapters.some(ch => ch.id === this.selectedChapterId);
            if (!chapterExists) {
              this.selectedChapterId = null;
            }
          }

          // Ensure "All Chapters" is selected by default if no selection exists
          if (this.selectedChapterId === undefined || this.selectedChapterId === 'null') {
            this.selectedChapterId = null;
          }

          // Ensure chapters are sorted by index
          this.chapters.sort((a, b) => a.index - b.index);

          // Initialize chapter states with current content
          this.initializeChapterStates();

          // Update line numbers after document loads
          setTimeout(() => this.updateLineNumbers(), 200);
        }
      });

    // Subscribe to active chapter changes
    this.chapterStateService.activeChapterId$
      .pipe(takeUntil(this.destroy$))
      .subscribe(activeChapterId => {
        this.activeChapterId = activeChapterId;
        if (activeChapterId) {
          // Restore cursor and selection when switching to a chapter
          this.restoreChapterState(activeChapterId);
        }
      });

    // Subscribe to selected sentence
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => {
        this.selectedSentenceId = sentence?.id || null;
      });

    // Subscribe to hovered emoji for highlighting
    this.characterHighlightService.hoveredEmoji$
      .pipe(takeUntil(this.destroy$))
      .subscribe(emoji => {
        console.log('👁️ [TEXT-VIEWER] Received hovered emoji:', emoji);
        this.hoveredEmoji = emoji;
        this.cdr.markForCheck();
      });

    // Subscribe to highlight color
    this.characterHighlightService.highlightColor$
      .pipe(takeUntil(this.destroy$))
      .subscribe(color => {
        this.highlightColor = color;
      });
  }

  ngAfterViewInit(): void {
    // Set up passive scroll listeners for better performance
    // Use a small delay to ensure ViewChild elements are available
    setTimeout(() => {
      this.setupScrollListeners();
    }, 100);
  }

  /**
   * Set up optimized scroll listeners with passive event handling
   */
  private setupScrollListeners(): void {
    const textContentEl = this.textContentContainer?.nativeElement;
    const lineNumbersEl = this.lineNumbersContainer?.nativeElement;

    if (textContentEl) {
      // Use passive listener for better scroll performance
      // Passive listeners allow browser to optimize scrolling
      textContentEl.addEventListener('scroll', (e) => {
        this.onTextContentScroll(e);
      }, { passive: true });
    }

    if (lineNumbersEl) {
      // Use passive listener for better scroll performance
      lineNumbersEl.addEventListener('scroll', (e) => {
        this.onLineNumbersScroll(e);
      }, { passive: true });
    }
  }

  ngAfterViewChecked(): void {
    // Update line numbers when view changes (content updates, resizing, etc.)
    this.updateLineNumbers();
  }

  ngOnDestroy(): void {
    // Save cursor state before destroying
    this.saveCurrentCursorState();

    // Remove event listener
    window.removeEventListener('navigateToChapter', this.navigateToChapterHandler);

    this.destroy$.next();
    this.destroy$.complete();
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
    }
    if (this.cursorSaveTimer) {
      clearTimeout(this.cursorSaveTimer);
    }
    if (this.lineNumberUpdateTimer) {
      clearTimeout(this.lineNumberUpdateTimer);
    }
    if (this.scrollSyncFrame !== null) {
      cancelAnimationFrame(this.scrollSyncFrame);
    }
  }

  /**
   * Initialize chapter states with current content
   */
  private initializeChapterStates(): void {
    if (!this.currentDocument) return;

    for (const chapter of this.chapters) {
      const chapterSentences = this.getChapterSentences(chapter.id);
      const chapterContent = chapterSentences.map(s => s.text).join(' ').trim();
      this.chapterStateService.initializeHistory(chapter.id, chapterContent);
    }
  }

  private triggerGlobalUndoSnapshot(sentenceId: string, newText: string): void {
    if (!this.currentDocument) return;

    const updatedFullContent = this.sentences
      .map(s => s.id === sentenceId ? newText : s.text)
      .join(' ');
    this.documentService.updateContentSilent(this.currentDocument.id, updatedFullContent);

  }

  private initializeOriginalAiText(): void {
    // Populate the original text map for AI sentences that aren't already tracked
    if (this.sentences) {
      this.sentences.forEach(s => {
        if (s.isAiGenerated && !this.aiOriginalTextMap.has(s.id)) {
          this.aiOriginalTextMap.set(s.id, s.text);
        }
      });
    }
  }

  /**
   * Save current cursor state for active chapter
   * NEW: Ob AI-Highlight für diesen Satz angezeigt werden soll.
   * Wenn User einmal tippt -> Highlight wird eingefroren und verschwindet.
   */
  shouldHighlightAi(sentence: Sentence): boolean {
    if (!this.showAiHighlight) return false;
    if (!sentence?.isAiGenerated) return false;
    return true;
  }

  getAiSegments(sentence: Sentence): Array<{ text: string, isAi: boolean }> {
    if (!sentence.isAiGenerated) {
      return [{ text: sentence.text, isAi: false }];
    }

    const originalText = this.aiOriginalTextMap.get(sentence.id);
    if (!originalText) {
      // Fallback if we don't have original text mapped (shouldn't happen often)
      return [{ text: sentence.text, isAi: true }];
    }

    // Check if the current text starts with the original AI text
    if (sentence.text.startsWith(originalText)) {
      const suffix = sentence.text.substring(originalText.length);
      const segments = [{ text: originalText, isAi: true }];
      if (suffix) {
        segments.push({ text: suffix, isAi: false });
      }
      return segments;
    }

    // If text changed completely, treat as modified (no AI highlight? or full?
    // User likely deleted/rewrote. Let's assume no highlight or minimal heuristic).
    // For now, if strict match fails, we return full text as NON-AI to avoid wrong highlight.
    return [{ text: sentence.text, isAi: false }];
  }

  // NOTE: freezeAiHighlightIfEdited removed as we support partial highlighting now.


  private saveCurrentCursorState(): void {
    if (!this.activeChapterId) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    const container = range.commonAncestorContainer;

    // Find the sentence element containing the cursor
    let sentenceElement: HTMLElement | null = null;
    let node: Node | null = container;

    while (node && node !== document.body) {
      if (node instanceof HTMLElement && node.hasAttribute('data-sentence-id')) {
        sentenceElement = node;
        break;
      }
      node = node.parentNode;
    }

    if (sentenceElement) {
      const sentenceId = sentenceElement.getAttribute('data-sentence-id');
      const sentence = this.sentences.find(s => s.id === sentenceId);

      // Only save if this sentence belongs to the active chapter
      if (sentence && sentence.chapterId === this.activeChapterId) {
        // Calculate offset within the sentence
        const textNode = sentenceElement.querySelector('.sentence-text');
        if (textNode) {
          const textRange = document.createRange();
          textRange.selectNodeContents(textNode);
          textRange.setEnd(range.endContainer, range.endOffset);
          const offset = textRange.toString().length;

          this.chapterStateService.saveCursor(this.activeChapterId, sentenceId!, offset);

          // Save selection if there's a selection
          if (!range.collapsed) {
            textRange.setStart(range.startContainer, range.startOffset);
            const startOffset = textRange.toString().length;
            this.chapterStateService.saveSelection(
              this.activeChapterId,
              sentenceId!,
              startOffset,
              sentenceId!,
              offset
            );
          } else {
            this.chapterStateService.clearSelection(this.activeChapterId);
          }
        }
      }
    }
  }

  /**
   * Restore cursor and selection for a chapter
   */
  private restoreChapterState(chapterId: string): void {
    // Use setTimeout to ensure DOM is ready
    setTimeout(() => {
      const cursor = this.chapterStateService.getCursor(chapterId);
      if (cursor && cursor.sentenceId) {
        const sentenceElement = document.querySelector(`[data-sentence-id="${cursor.sentenceId}"]`);
        if (sentenceElement) {
          // In "All Chapters" view, scroll to the chapter section if needed
          if (this.selectedChapterId === null) {
            const chapterSection = sentenceElement.closest('.chapter-section');
            if (chapterSection) {
              chapterSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
          }

          const textElement = sentenceElement.querySelector('.sentence-text');
          if (textElement instanceof HTMLElement) {
            // Focus the element
            textElement.focus();

            // Restore cursor position
            const range = document.createRange();
            const textNode = textElement.firstChild || textElement;
            if (textNode.nodeType === Node.TEXT_NODE) {
              const offset = Math.min(cursor.offset, textNode.textContent?.length || 0);
              range.setStart(textNode, offset);
              range.setEnd(textNode, offset);
            } else {
              range.selectNodeContents(textElement);
              range.collapse(true);
            }

            const selection = window.getSelection();
            if (selection) {
              selection.removeAllRanges();
              selection.addRange(range);
            }
          }
        }
      } else if (this.selectedChapterId === null) {
        // If no cursor but in "All Chapters" view, scroll to chapter section
        const chapterSection = document.querySelector(`[data-chapter-id="${chapterId}"]`);
        if (chapterSection) {
          chapterSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }, 50);
  }

  onSentenceClick(sentence: Sentence): void {
    this.documentService.selectSentence(sentence);

    // Set active chapter when user clicks on a sentence
    if (sentence.chapterId) {
      this.chapterStateService.setActiveChapter(sentence.chapterId);
    }

    // Save cursor state after a short delay
    this.debouncedSaveCursor();
  }

  onSentenceInput(sentence: Sentence, newText: string): void {
    this.charsSinceLastSnapshot++;
    // Set active chapter when user types in a sentence
    if (sentence.chapterId) {
      this.chapterStateService.setActiveChapter(sentence.chapterId);
    }

    // Save cursor state
    this.debouncedSaveCursor();

    // Clear any existing timer
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
    }

    // CRITICAL: Only process updates for sentences in the active chapter
    if (sentence.chapterId !== this.activeChapterId) {
      return; // Ignore input events from other chapters
    }

    const trimmedText = newText.trim();
    const trimmedOldText = sentence.text.trim();

    // Check if user just typed sentence-ending punctuation (. ! ?)
    // This detects when a sentence is complete and should be split
    const lastChar = trimmedText.slice(-1);
    const endsWithPunctuation = /[.!?]/.test(lastChar);
    const oldEndsWithPunctuation = /[.!?]/.test(trimmedOldText.slice(-1));
    const justCompletedSentence = endsWithPunctuation && !oldEndsWithPunctuation;

    // Check if text contains multiple sentences (split by .!? followed by space)
    const hasMultipleSentences = trimmedText.split(/[.!?]\s+(?=\S)/).length > 1;

    if (this.charsSinceLastSnapshot >= 20) {
      this.triggerGlobalUndoSnapshot(sentence.id, trimmedText);
    }

    if (justCompletedSentence || hasMultipleSentences) {
      // Sentence just completed - immediately split and trigger emoji generation
      // Clear the debounce timer since we're processing immediately
      if (this.sentenceUpdateTimer) {
        clearTimeout(this.sentenceUpdateTimer);
        this.sentenceUpdateTimer = null;
      }

      // Update chapter content to trigger sentence splitting
      const currentDoc = this.documentService.getCurrentDocument();
      if (currentDoc && sentence.chapterId) {
        // Get all sentences for this chapter
        const chapterSentences = this.getChapterSentences(sentence.chapterId);
        const updatedSentences = chapterSentences.map(s =>
          s.id === sentence.id ? trimmedText : s.text
        );
        const chapterText = updatedSentences.join(' ').trim();

        // Update chapter history
        this.chapterStateService.addHistoryEntry(sentence.chapterId, chapterText);

        // CRITICAL: Update only this chapter's content, preserving others
        // This will trigger backend re-parsing which splits sentences
        this.documentService.updateChapterContent(currentDoc.id, sentence.chapterId, chapterText);

        // After sentence splitting, trigger emoji generation for the completed sentence(s)
        // Wait for document to reload, then generate emojis for newly completed sentences
        setTimeout(() => {
          const updatedDoc = this.documentService.getCurrentDocument();
          if (updatedDoc && sentence.chapterId) {
            const updatedChapterSentences = updatedDoc.sentences
              .filter(s => s.chapterId === sentence.chapterId)
              .sort((a, b) => a.index - b.index);

            // Find the sentence(s) that were just completed
            // The last sentence in the chapter is likely the one just completed
            if (updatedChapterSentences.length > 0) {
              const lastSentence = updatedChapterSentences[updatedChapterSentences.length - 1];

              // Only generate emojis if the sentence ends with punctuation and has no emojis yet
              if (lastSentence && /[.!?]$/.test(lastSentence.text.trim()) &&
                  (!lastSentence.emojis || lastSentence.emojis.length === 0)) {
                this.autoGenerateEmojisForSentence(lastSentence);
              }
            }
          }
        }, 500); // Wait for document reload
      }
    } else {
      // Normal typing - debounced update without sentence splitting
      this.sentenceUpdateTimer = setTimeout(() => {
        if (trimmedText !== trimmedOldText) {
          // Only update sentence text (not full document re-parse) while user is typing
          this.documentService.updateSentenceText(sentence.id, trimmedText);
          // Update line numbers after text change
          this.updateLineNumbers();
        }
      }, 1500); // Longer delay to avoid interrupting typing
    }
  }

  onSentenceBlur(sentence: Sentence, newText: string): void {
    // Save cursor state on blur
    this.saveCurrentCursorState();

    // Clear any pending timer
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
      this.sentenceUpdateTimer = null;
    }

    const trimmedNewText = newText.trim();
    const trimmedOldText = sentence.text.trim();

    // CRITICAL: Only process updates for sentences in the active chapter
    if (sentence.chapterId !== this.activeChapterId) {
      return; // Ignore blur events from other chapters
    }

    if (trimmedNewText !== trimmedOldText) {
      // Check if text contains sentence-ending punctuation that could create new sentences
      const hasMultipleSentences = trimmedNewText.split(/[.!?]\s+(?=\S)/).length > 1;

      if (hasMultipleSentences && sentence.chapterId) {
        // Re-parse only the active chapter's content
        const currentDoc = this.documentService.getCurrentDocument();
        if (currentDoc) {
          // Get all sentences for this chapter
          const chapterSentences = this.getChapterSentences(sentence.chapterId);
          const updatedSentences = chapterSentences.map(s =>
            s.id === sentence.id ? trimmedNewText : s.text
          );
          const chapterText = updatedSentences.join(' ').trim();

          // Update chapter content in history
          this.chapterStateService.addHistoryEntry(sentence.chapterId, chapterText);

          // CRITICAL: Update only this chapter's content, preserving others
          this.documentService.updateChapterContent(currentDoc.id, sentence.chapterId, chapterText);
        }
      } else {
        // Just update this sentence text without re-parsing
        this.documentService.updateSentenceText(sentence.id, trimmedNewText);

        // Update chapter history
        if (sentence.chapterId) {
          const chapterSentences = this.getChapterSentences(sentence.chapterId);
          const chapterText = chapterSentences.map(s => s.text).join(' ').trim();
          this.chapterStateService.addHistoryEntry(sentence.chapterId, chapterText);
        }

        // Update line numbers after text change
        this.updateLineNumbers();
      }
    }
  }

  /**
   * Debounced cursor save to avoid excessive state updates
   */
  private debouncedSaveCursor(): void {
    if (this.cursorSaveTimer) {
      clearTimeout(this.cursorSaveTimer);
    }
    this.cursorSaveTimer = setTimeout(() => {
      this.saveCurrentCursorState();
    }, 100);
  }

  /**
   * Handle sentence focus - set active chapter and save cursor
   */
  onSentenceFocus(sentence: Sentence, event: FocusEvent): void {
    // Ensure we track selection on focus, so highlighting logic works correctly
    if (this.selectedSentenceId !== sentence.id) {
      this.documentService.selectSentence(sentence);
    }

    if (sentence.chapterId) {
      this.chapterStateService.setActiveChapter(sentence.chapterId);
    }

    // Save cursor state immediately on focus
    setTimeout(() => {
      this.saveCurrentCursorState();
    }, 10);
  }

  /**
   * Handle keyup events to save cursor position
   */
  onSentenceKeyUp(sentence: Sentence, event: KeyboardEvent): void {
    // CRITICAL: Only process keyup for sentences in the active chapter
    if (sentence.chapterId !== this.activeChapterId) {
      return; // Ignore keyup events from other chapters
    }

    // Save cursor state on keyup (arrow keys, etc.)
    this.debouncedSaveCursor();

    // ENTER key should NOT trigger sentence splitting - it's just a line break
    // Sentence boundaries are defined by . ! ? only
    if (event.key === 'Enter') {
      // Prevent default behavior (new paragraph) and insert a space instead
      event.preventDefault();
      const selection = window.getSelection();
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        const textNode = document.createTextNode(' ');
        range.insertNode(textNode);
        range.setStartAfter(textNode);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
      }
    }
  }

  /**
   * Auto-generate emojis for a completed sentence
   * Only generates if sentence belongs to active chapter
   */
  private autoGenerateEmojisForSentence(sentence: Sentence): void {
    // CRITICAL: Only generate emojis for sentences in the active chapter
    if (sentence.chapterId !== this.activeChapterId) {
      return;
    }

    const currentDoc = this.documentService.getCurrentDocument();
    if (!currentDoc) return;

    // Check if sentence already has emojis
    if (sentence.emojis && sentence.emojis.length > 0) {
      return; // Skip if emojis already exist
    }

    // Generate emojis for this sentence
    this.aiService.generateEmojisFromText({
      documentId: currentDoc.id,
      sentenceId: sentence.id,
      text: sentence.text
    }).subscribe({
      next: (response) => {
        // Only update if sentence still belongs to active chapter
        const updatedDoc = this.documentService.getCurrentDocument();
        if (updatedDoc) {
          const updatedSentence = updatedDoc.sentences.find(s => s.id === sentence.id);
          if (updatedSentence && updatedSentence.chapterId === this.activeChapterId) {
            this.documentService.updateSentenceEmojis(sentence.id, response.emojis || []);
          }
        }
      },
      error: (err) => {
        // Silently fail - emoji generation is optional
        console.debug('Auto emoji generation failed (non-critical):', err);
      }
    });
  }

  isSelected(sentenceId: string): boolean {
    return this.selectedSentenceId === sentenceId;
  }

  toggleViewMode(): void {
    this.viewMode = this.viewMode === 'text' ? 'emoji' : 'text';
    // Update line numbers when switching to text view
    if (this.viewMode === 'text') {
      setTimeout(() => this.updateLineNumbers(), 100);
    }
  }

  toggleAiHighlight(): void {
    this.showAiHighlight = !this.showAiHighlight;
  }

  isAiGenerated(sentence: Sentence): boolean {
    return !!sentence.isAiGenerated;
  }

  /**
   * Find character mentions in a sentence and return segments with character info
   */
  getTextSegments(sentenceText: string): Array<{ text: string, character: Character | null }> {
    if (!this.characters || this.characters.length === 0) {
      return [{ text: sentenceText, character: null }];
    }

    const segments: Array<{ text: string, character: Character | null }> = [];
    let lastIndex = 0;

    // Build a list of all character matches with their positions
    const matches: Array<{ start: number, end: number, character: Character }> = [];

    for (const character of this.characters) {
      // Check name and all aliases
      const searchTerms = [character.name, ...character.aliases];

      for (const term of searchTerms) {
        const regex = new RegExp(`\\b${term}\\b`, 'gi');
        let match;

        while ((match = regex.exec(sentenceText)) !== null) {
          matches.push({
            start: match.index,
            end: match.index + match[0].length,
            character: character
          });
        }
      }
    }

    // Sort matches by position
    matches.sort((a, b) => a.start - b.start);

    // Remove overlapping matches (keep first occurrence)
    const filteredMatches: Array<{ start: number, end: number, character: Character }> = [];
    for (const match of matches) {
      const overlaps = filteredMatches.some(existing =>
        (match.start >= existing.start && match.start < existing.end) ||
        (match.end > existing.start && match.end <= existing.end)
      );
      if (!overlaps) {
        filteredMatches.push(match);
      }
    }

    // Build segments from matches
    if (filteredMatches.length === 0) {
      return [{ text: sentenceText, character: null }];
    }

    filteredMatches.forEach((match) => {
      if (match.start > lastIndex) {
        segments.push({
          text: sentenceText.substring(lastIndex, match.start),
          character: null
        });
      }

      // Add matched text with character
      segments.push({
        text: sentenceText.substring(match.start, match.end),
        character: match.character
      });

      lastIndex = match.end;
    });

    // Add remaining text
    if (lastIndex < sentenceText.length) {
      segments.push({
        text: sentenceText.substring(lastIndex),
        character: null
      });
    }

    return segments;
  }

  /**
   * Check if a sentence contains mentions of a specific character
   */
  sentenceHasCharacter(sentence: Sentence, characterId: string | null): boolean {
    if (!characterId || !this.characters) {
      return false;
    }

    const character = this.characters.find(c => c.id === characterId);
    if (!character) {
      return false;
    }

    const searchTerms = [character.name, ...character.aliases];
    const text = sentence.text.toLowerCase();


    return searchTerms.some(term => {
      const regex = new RegExp(`\\b${term.toLowerCase()}\\b`);
      return regex.test(text);
    });
  }

  /**
   * Check if a sentence contains the hovered emoji
   */
  sentenceHasHoveredEmoji(sentence: Sentence): boolean {
    if (!this.hoveredEmoji) return false;
    return sentence.emojis.includes(this.hoveredEmoji);
  }

  /**
   * Get text segments with word-level highlighting for hovered emoji
   * Returns array of {text, isHighlighted}
   */
  getHighlightedSegments(sentence: Sentence): Array<{ text: string, isHighlighted: boolean }> {
    if (!this.hoveredEmoji) {
      return [{ text: sentence.text, isHighlighted: false }];
    }

    // Collect all phrases to highlight for this emoji
    let phrases: string[] = [];

    // STRATEGY 1: Check if this emoji belongs to a CHARACTER
    const charactersWithEmoji = this.characters.filter(c => c.emoji === this.hoveredEmoji);

    if (charactersWithEmoji.length > 0) {
      // This emoji IS a character - use character's word phrases
      // Combines all phrases from all characters using this emoji (e.g., "Hero" and "Red Hero" both use 🦸)
      for (const character of charactersWithEmoji) {
        if (character.wordPhrases && character.wordPhrases.length > 0) {
          phrases.push(...character.wordPhrases);
        }
      }
    } else {
      // STRATEGY 2: This emoji is a RECURRING THEME (not promoted to character yet)
      // Use the sentence's emoji_mappings to find what words it represents
      if (sentence.emojis.includes(this.hoveredEmoji) && sentence.emojiMappings && this.hoveredEmoji in sentence.emojiMappings) {
        phrases = sentence.emojiMappings[this.hoveredEmoji] || [];
      }
    }

    if (phrases.length === 0) {
      // No mapping available - don't highlight anything
      return [{ text: sentence.text, isHighlighted: false }];
    }

    // Find all phrase occurrences in the text using word boundaries
    const segments: Array<{ text: string, isHighlighted: boolean }> = [];

    // Build a list of matches with positions
    const matches: Array<{ start: number, end: number, phrase: string }> = [];
    for (const phrase of phrases) {
      // Use word boundary regex to avoid false matches (e.g., "hero" shouldn't match "heroic")
      const escapedPhrase = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`\\b${escapedPhrase}\\b`, 'gi');
      let match;
      while ((match = regex.exec(sentence.text)) !== null) {
        matches.push({
          start: match.index,
          end: match.index + match[0].length,
          phrase: match[0]
        });
      }
    }

    // Sort matches by position and remove overlaps
    matches.sort((a, b) => a.start - b.start);
    const filteredMatches: Array<{ start: number, end: number }> = [];
    for (const match of matches) {
      const overlaps = filteredMatches.some(existing =>
        (match.start >= existing.start && match.start < existing.end) ||
        (match.end > existing.start && match.end <= existing.end)
      );
      if (!overlaps) {
        filteredMatches.push(match);
      }
    }

    // Build segments
    if (filteredMatches.length === 0) {
      return [{ text: sentence.text, isHighlighted: false }];
    }

    let lastIndex = 0;
    for (const match of filteredMatches) {
      // Add text before match
      if (match.start > lastIndex) {
        segments.push({
          text: sentence.text.substring(lastIndex, match.start),
          isHighlighted: false
        });
      }
      // Add highlighted match
      segments.push({
        text: sentence.text.substring(match.start, match.end),
        isHighlighted: true
      });
      lastIndex = match.end;
    }

    // Add remaining text
    if (lastIndex < sentence.text.length) {
      segments.push({
        text: sentence.text.substring(lastIndex),
        isHighlighted: false
      });
    }

    return segments;
  }

  /**
   * Get filtered sentences based on selected chapter
   */
  getFilteredSentences(): Sentence[] {
    if (this.selectedChapterId === null) {
      // Show all chapters
      return this.sentences;
    } else {
      // Show only selected chapter
      return this.sentences.filter(s => s.chapterId === this.selectedChapterId);
    }
  }

  /**
   * Get unassigned sentences (sentences without a chapter)
   */
  getUnassignedSentences(): Sentence[] {
    return this.sentences.filter(s => !s.chapterId);
  }

  /**
   * Check if there are unassigned sentences
   */
  hasUnassignedSentences(): boolean {
    return this.sentences.some(s => !s.chapterId);
  }

  /**
   * Get sentences for a specific chapter
   */
  getChapterSentences(chapterId: string): Sentence[] {
    return this.sentences.filter(s => s.chapterId === chapterId);
  }

  /**
   * Check if a chapter has sentences
   */
  chapterHasSentences(chapterId: string): boolean {
    return this.sentences.some(s => s.chapterId === chapterId);
  }

  /**
   * Get body sentences (excluding chapter titles) for line numbering
   * Returns all sentences that are currently visible based on chapter filter
   * Sorted by index to maintain proper order across chapters
   */
  getBodySentences(): Sentence[] {
    if (this.chapters.length === 0) {
      // No chapters - return all sentences sorted by index
      return [...this.sentences].sort((a, b) => a.index - b.index);
    }

    if (this.selectedChapterId === null) {
      // "All Chapters" selected - return all sentences from all chapters, sorted by index
      // This ensures continuous line numbering across chapters
      return [...this.sentences].sort((a, b) => a.index - b.index);
    } else {
      // Single chapter selected - return only that chapter's sentences, sorted by index
      return this.sentences
        .filter(s => s.chapterId === this.selectedChapterId)
        .sort((a, b) => a.index - b.index);
    }
  }

  /**
   * Get all visible sentences for the current view (respects chapter filter)
   * This includes all sentences that should be displayed
   */
  getVisibleSentences(): Sentence[] {
    if (this.chapters.length === 0) {
      return this.sentences;
    }

    if (this.selectedChapterId === null) {
      // Show all chapters - return all sentences
      return this.sentences;
    } else {
      // Show single chapter - return only that chapter's sentences
      return this.sentences.filter(s => s.chapterId === this.selectedChapterId);
    }
  }

  /**
   * Add a new chapter
   */
  addChapter(): void {
    if (!this.currentDocument) return;

    this.documentService.createChapter(this.currentDocument.id).subscribe({
      next: (newChapter) => {
        // Also set as selected for view
        this.selectedChapterId = newChapter.id;

        // Wait for document to reload, then initialize chapter state and set as active
        // The document reload happens in createChapter, so we need to wait for it
        setTimeout(() => {
          const updatedDoc = this.documentService.getCurrentDocument();
          if (updatedDoc) {
            // Get the chapter's sentences
            const chapterSentences = updatedDoc.sentences
              .filter(s => s.chapterId === newChapter.id)
              .sort((a, b) => a.index - b.index);

            if (chapterSentences.length > 0) {
              // Initialize chapter history with content
              const chapterContent = chapterSentences.map(s => s.text).join(' ').trim();
              this.chapterStateService.initializeHistory(newChapter.id, chapterContent);

              // Set cursor to start of first sentence (position 0) BEFORE setting active chapter
              // This ensures the cursor is saved before restoreChapterState is called
              const firstSentence = chapterSentences[0];
              this.chapterStateService.saveCursor(newChapter.id, firstSentence.id, 0);

              // Clear any selection
              this.chapterStateService.clearSelection(newChapter.id);

              // Now set the chapter as active (this will trigger restoreChapterState)
              this.chapterStateService.setActiveChapter(newChapter.id);
            } else {
              // No sentences yet, just set as active
              this.chapterStateService.setActiveChapter(newChapter.id);
            }
          }
        }, 100); // Small delay to ensure document is reloaded
      },
      error: (err) => {
        console.error('Error creating chapter:', err);
      }
    });
  }

  /**
   * Start editing a chapter title
   */
  startEditingChapter(chapter: Chapter): void {
    this.editingChapterId = chapter.id;
    // Extract just the title part (after the number) for editing
    // If title is "01 Title", allow editing "Title" part
    const match = chapter.title.match(/^\d+\s+(.+)$/);
    this.editingChapterTitle = match ? match[1] : chapter.title;
  }

  /**
   * Save chapter title
   */
  saveChapterTitle(chapter: Chapter): void {
    if (!this.currentDocument || !this.editingChapterTitle.trim()) return;

    // Preserve the chapter number format (01, 02, etc.)
    const chapterNum = (chapter.index + 1).toString().padStart(2, '0');
    const newTitle = `${chapterNum} ${this.editingChapterTitle.trim()}`;

    this.documentService.updateChapter(
      this.currentDocument.id,
      chapter.id,
      newTitle
    ).subscribe({
      next: () => {
        this.editingChapterId = null;
        this.editingChapterTitle = '';
      },
      error: (err) => {
        console.error('Error updating chapter:', err);
      }
    });
  }

  /**
   * Cancel editing chapter title
   */
  cancelEditingChapter(): void {
    this.editingChapterId = null;
    this.editingChapterTitle = '';
  }

  /**
   * Handle Enter key on chapter title
   */
  onChapterTitleKeyDown(event: KeyboardEvent, chapter: Chapter): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.saveChapterTitle(chapter);
      // Focus the first sentence in this chapter or create a placeholder
      setTimeout(() => {
        const chapterSentences = this.getChapterSentences(chapter.id);
        if (chapterSentences.length > 0) {
          const firstSentence = chapterSentences[0];
          const element = document.querySelector(`[data-sentence-id="${firstSentence.id}"]`);
          if (element instanceof HTMLElement) {
            element.focus();
          }
        }
      }, 100);
    } else if (event.key === 'Escape') {
      this.cancelEditingChapter();
    }
  }

  /**
   * Select a chapter to filter (view mode)
   */
  selectChapter(chapterId: string | null): void {
    // Ensure null is properly handled (ngValue should handle this, but be safe)
    this.selectedChapterId = chapterId === 'null' ? null : chapterId;

    // When filtering to a single chapter, also set it as active
    if (this.selectedChapterId) {
      this.chapterStateService.setActiveChapter(this.selectedChapterId);
    } else {
      // When viewing "All Chapters", keep the last active chapter or set first chapter as active
      const currentActive = this.chapterStateService.getActiveChapterId();
      if (!currentActive && this.chapters.length > 0) {
        this.chapterStateService.setActiveChapter(this.chapters[0].id);
      }
    }

    // Update line numbers when chapter selection changes
    setTimeout(() => this.updateLineNumbers(), 100);
  }

  /**
   * Check if placeholder should be shown
   */
  shouldShowPlaceholder(chapterId: string): boolean {
    // Show placeholder only if chapter is new and no sentences exist anywhere in the document
    const chapterSentences = this.getChapterSentences(chapterId);
    return chapterSentences.length === 0 && this.sentences.length === 0;
  }

  /**
   * Handle placeholder click - focus the editor
   */
  onPlaceholderClick(chapterId: string | null): void {
    // Placeholder is already contenteditable, so clicking will focus it
  }

  /**
   * Handle placeholder input - create sentence from text
   */
  onPlaceholderInput(event: Event, chapterId: string | null): void {
    const target = event.target as HTMLElement;
    const text = target.innerText.trim();

    // Set active chapter when user types in placeholder
    if (chapterId) {
      this.chapterStateService.setActiveChapter(chapterId);
    }

    // Remove placeholder text if user is typing
    if (target.innerText === 'Start typing here...') {
      target.innerText = '';
    }

    // Save cursor state
    this.debouncedSaveCursor();
  }

  /**
   * Handle placeholder blur - create sentence from placeholder text
   */
  onPlaceholderBlur(event: Event, chapterId: string | null): void {
    const target = event.target as HTMLElement;
    const text = target.innerText.trim();

    if (text && text !== 'Start typing here...' && this.currentDocument && chapterId) {
      // Create a sentence from the placeholder text
      // CRITICAL: Only update the specific chapter's content
      const chapterSentences = this.getChapterSentences(chapterId);
      const chapterText = chapterSentences.map(s => s.text).join(' ').trim();
      const newChapterText = chapterText ? `${chapterText} ${text}` : text;

      // Update chapter history
      this.chapterStateService.addHistoryEntry(chapterId, newChapterText);

      // CRITICAL: Update only this chapter's content, preserving others
      this.documentService.updateChapterContent(this.currentDocument.id, chapterId, newChapterText);

      // Clear placeholder after content is added
      target.innerText = '';
    }

    // Restore placeholder if empty (but only if this chapter has no sentences)
    if (!text || text === 'Start typing here...') {
      if (chapterId) {
        const chapterSentences = this.getChapterSentences(chapterId);
        if (chapterSentences.length === 0) {
          target.innerText = 'Start typing here...';
        } else {
          // Hide placeholder if chapter has sentences
          target.style.display = 'none';
        }
      } else {
        // No chapter - restore if no sentences exist
        if (this.sentences.length === 0) {
          target.innerText = 'Start typing here...';
        } else {
          target.style.display = 'none';
        }
      }
    }
  }

  /**
   * Get active chapter ID (the one being edited)
   */
  getActiveChapterId(): string | null {
    return this.chapterStateService.getActiveChapterId();
  }

  /**
   * Get content for a specific chapter
   */
  getChapterContent(chapterId: string): string {
    const chapterSentences = this.getChapterSentences(chapterId);
    return chapterSentences.map(s => s.text).join(' ').trim();
  }

  /**
   * Get active chapter's content (for AI operations)
   */
  getActiveChapterContent(): string {
    const activeChapterId = this.getActiveChapterId();
    if (!activeChapterId) {
      return '';
    }
    return this.getChapterContent(activeChapterId);
  }

  /**
   * Synchronize scroll between line numbers and text content
   * Line numbers scrollbar is hidden but still functional
   * Uses direct scrollTop matching for perfect alignment
   */
  onLineNumbersScroll(event: Event): void {
    if (this.isScrolling) return;

    const lineNumbersEl = this.lineNumbersContainer?.nativeElement;
    const textContentEl = this.textContentContainer?.nativeElement;

    if (lineNumbersEl && textContentEl) {
      // Cancel any pending scroll sync
      if (this.scrollSyncFrame !== null) {
        cancelAnimationFrame(this.scrollSyncFrame);
      }

      // Use requestAnimationFrame for smooth, performant scrolling
      this.scrollSyncFrame = requestAnimationFrame(() => {
        this.isScrolling = true;

        // Direct scrollTop matching for perfect alignment
        // Both containers should have the same scrollTop value
        textContentEl.scrollTop = lineNumbersEl.scrollTop;

        this.isScrolling = false;
        this.scrollSyncFrame = null;
      });
    }
  }

  /**
   * Synchronize scroll between text content and line numbers
   * Single scrollbar on content, line numbers follow (scrollbar hidden)
   * Uses direct scrollTop matching for perfect alignment
   */
  onTextContentScroll(event: Event): void {
    if (this.isScrolling) return;

    const lineNumbersEl = this.lineNumbersContainer?.nativeElement;
    const textContentEl = this.textContentContainer?.nativeElement;

    if (lineNumbersEl && textContentEl) {
      // Cancel any pending scroll sync
      if (this.scrollSyncFrame !== null) {
        cancelAnimationFrame(this.scrollSyncFrame);
      }

      // Use requestAnimationFrame for smooth, performant scrolling
      this.scrollSyncFrame = requestAnimationFrame(() => {
        this.isScrolling = true;

        // Direct scrollTop matching for perfect alignment
        // Both containers should have the same scrollTop value
        lineNumbersEl.scrollTop = textContentEl.scrollTop;

        this.isScrolling = false;
        this.scrollSyncFrame = null;
      });
    }
  }

  /**
   * Calculate and update line numbers based on actual rendered text lines
   * Excludes chapter titles and only counts flowing text content
   * Aligns line numbers with the first line of flowing text
   */
  private updateLineNumbers(): void {
    // Debounce updates to avoid excessive recalculations
    if (this.lineNumberUpdateTimer) {
      clearTimeout(this.lineNumberUpdateTimer);
    }

    this.lineNumberUpdateTimer = setTimeout(() => {
      const textContentEl = this.textContentContainer?.nativeElement;
      const lineNumbersEl = this.lineNumbersContainer?.nativeElement;
      if (!textContentEl || this.viewMode !== 'text') {
        this.lineNumbers = [];
        return;
      }

      // Get all chapter-sentences containers (excludes chapter titles)
      const chapterSentencesContainers = textContentEl.querySelectorAll('.chapter-sentences');

      // Get computed styles for accurate line height calculation
      const computedStyle = window.getComputedStyle(textContentEl);
      const lineHeight = parseFloat(computedStyle.lineHeight) || parseFloat(computedStyle.fontSize) * 2;

      let totalTextHeight = 0;
      let firstTextLineOffset = 0;

      if (chapterSentencesContainers.length > 0) {
        // Measure chapter-sentences containers (excludes chapter titles)
        let isFirstContainer = true;
        chapterSentencesContainers.forEach((container: Element) => {
          const htmlContainer = container as HTMLElement;
          // Get the actual rendered height of the text content
          const containerHeight = htmlContainer.scrollHeight || htmlContainer.offsetHeight;
          totalTextHeight += containerHeight;

          // Calculate offset to first text line (account for chapter title if it's the first chapter)
          if (isFirstContainer && this.chapters.length > 0) {
            const chapterSection = htmlContainer.closest('.chapter-section');
            if (chapterSection) {
              const titleWrapper = chapterSection.querySelector('.chapter-title-wrapper');
              if (titleWrapper) {
                const titleHeight = (titleWrapper as HTMLElement).offsetHeight;
                firstTextLineOffset = titleHeight;
              }
            }
            isFirstContainer = false;
          }
        });
      } else {
        // Fallback: measure sentence elements directly (for documents without chapters)
        const sentenceElements = textContentEl.querySelectorAll('.sentence-text');
        if (sentenceElements.length === 0) {
          this.lineNumbers = [];
          return;
        }

        // Create a temporary container to measure wrapped text accurately
        const tempContainer = document.createElement('div');
        tempContainer.style.position = 'absolute';
        tempContainer.style.visibility = 'hidden';
        tempContainer.style.width = (textContentEl.clientWidth - parseFloat(computedStyle.paddingLeft) - parseFloat(computedStyle.paddingRight)) + 'px';
        tempContainer.style.fontSize = computedStyle.fontSize;
        tempContainer.style.fontFamily = computedStyle.fontFamily;
        tempContainer.style.lineHeight = computedStyle.lineHeight;
        tempContainer.style.whiteSpace = 'normal';
        tempContainer.style.wordWrap = 'break-word';

        // Collect all sentence text
        const allText = Array.from(sentenceElements)
          .map((el: Element) => (el as HTMLElement).textContent || '')
          .join(' ');

        tempContainer.textContent = allText;
        document.body.appendChild(tempContainer);
        totalTextHeight = tempContainer.offsetHeight;
        document.body.removeChild(tempContainer);
      }

      // Calculate number of lines based on actual text height
      // Use the actual scrollHeight of the text content for accurate line counting
      let actualContentHeight = totalTextHeight;

      // Get the actual scrollable height of the text content
      // This accounts for all padding, margins, and actual rendered content
      const textScrollHeight = textContentEl.scrollHeight;
      const textPaddingTop = parseFloat(getComputedStyle(textContentEl).paddingTop) || 0;
      const textPaddingBottom = parseFloat(getComputedStyle(textContentEl).paddingBottom) || 0;

      // Calculate the actual content height (excluding padding)
      actualContentHeight = textScrollHeight - textPaddingTop - textPaddingBottom;

      // Calculate number of lines - each line is exactly lineHeight tall
      const numberOfLines = Math.max(1, Math.ceil(actualContentHeight / lineHeight));

      // Generate line numbers array
      this.lineNumbers = Array.from({ length: numberOfLines }, (_, i) => i + 1);

      // Ensure line numbers container has the same total height as text content
      // This ensures perfect scroll synchronization
      if (lineNumbersEl && textContentEl) {
        // Set padding-top to match any offset in text content (e.g., chapter titles)
        if (firstTextLineOffset > 0) {
          lineNumbersEl.style.paddingTop = `${firstTextLineOffset}px`;
        } else {
          lineNumbersEl.style.paddingTop = '0px';
        }

        // Ensure padding-bottom matches exactly
        const textPaddingBottom = parseFloat(getComputedStyle(textContentEl).paddingBottom);
        lineNumbersEl.style.paddingBottom = `${textPaddingBottom}px`;

        // Force a reflow to ensure heights are calculated
        void lineNumbersEl.offsetHeight;
        void textContentEl.offsetHeight;

        // After a brief delay, verify and sync scroll positions
        setTimeout(() => {
          // If scroll positions are out of sync, fix them
          if (Math.abs(lineNumbersEl.scrollTop - textContentEl.scrollTop) > 1) {
            // Sync to text content's scroll position (text content is the source of truth)
            lineNumbersEl.scrollTop = textContentEl.scrollTop;
          }
        }, 0);
      }

      this.cdr.markForCheck();
    }, 150); // Debounce for 150ms to allow DOM to settle
  }

  /**
   * Track by function for chapter ngFor to improve performance
   */
  trackByChapterId(index: number, chapter: Chapter): string {
    return chapter.id;
  }

  trackBySentenceId(index: number, sentence: Sentence): string {
  return sentence.id;
  }


}
