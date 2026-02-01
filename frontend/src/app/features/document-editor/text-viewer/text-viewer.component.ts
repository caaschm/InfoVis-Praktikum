import { Component, OnInit, OnDestroy, Input, ViewChild, ElementRef, AfterViewInit, AfterViewChecked, HostListener, ChangeDetectorRef, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription, combineLatest } from 'rxjs';
import { debounceTime, takeUntil, distinctUntilChanged } from 'rxjs/operators';
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
  hoveredSentence: Sentence | null = null; // Sentence currently being hovered
  hoveredSentenceForTooltip: string | null = null; // Sentence hovered for emoji tooltip display
  generatingSentenceId: string | null = null; // Sentence currently generating emojis
  hoveredEmoji: string | null = null;
  highlightColor: string = '#999999';
  highlightedSentenceId: string | null = null; // Sentence ID to highlight with specific color
  sentenceHighlightColor: string = '#999999'; // Color for sentence-specific highlighting
  viewMode: 'text' | 'emoji' = 'text'; // Toggle between text and emoji-only view
  showAiHighlight: boolean = false; // Toggle for AI highlight mode
  selectedChapterId: string | null = null; // null means "All Chapters" (view filter)
  activeChapterId: string | null = null; // The chapter currently being edited (active editor)
  editingChapterId: string | null = null; // Chapter title being edited
  editingChapterTitle: string = '';
  editingChapterEmojiId: string | null = null; // Chapter emoji being edited
  editingChapterEmoji: string = '';
  // AI title suggestion state
  suggestingTitleForChapterId: string | null = null;
  aiTitleSuggestion: string | null = null;
  titleSuggestionLoading: boolean = false;
  // AI emoji suggestion state
  suggestingEmojiForChapterId: string | null = null;
  aiEmojiSuggestion: string | null = null;
  emojiSuggestionLoading: boolean = false;

  // Add menu dropdown state
  showAddMenu: boolean = false;

  commonEmojis = [
    '📖', '📚', '📝', '✨', '⭐', '💫', '🔥', '💎',
    '⚔️', '🛡️', '👑', '🏰', '🌙', '☀️', '🌈', '🌊',
    '🌲', '🌺', '🌸', '🍃', '🍀', '🌍', '🗺️', '🎭'
  ];
  private aiGeneratedSentenceIds = new Set<string>(); // Track AI-generated sentences
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;
  private cursorSaveTimer: any = null;
  private isScrolling = false; // Flag to prevent scroll event loops
  private scrollSyncFrame: number | null = null; // RAF ID for scroll sync
  lineNumbers: number[] = []; // Array of line numbers for actual text lines
  private lineNumberUpdateTimer: any = null;
  private charsSinceLastSnapshot = 0;
  private isLocalTyping = false;



  /**
   * KEY FIX:
   * Sobald ein AI-Satz vom User editiert wird, frieren wir das AI-Highlight ein
   * (nur UI), damit das Highlight NICHT "weiterwandert".
   */
  private aiHighlightFrozenForSentenceIds = new Set<string>();

  @ViewChild('lineNumbersContainer') lineNumbersContainer?: ElementRef<HTMLElement>;
  @ViewChild('textContentContainer') textContentContainer?: ElementRef<HTMLElement>;

  // Debounce for cursor saving
  private cursorSaveSubject = new Subject<void>();

  // Debounce for local typing state to prevent Angular/Browser fights
  private resetLocalTypingTimer: any;

  @Input()
  set activeTab(value: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'storyarc') {
    // When story-arc tab is activated, reset to "All Chapters" view
    if (value === 'storyarc') {
      this.selectedChapterId = null;
    }
  }

  constructor(
    private documentService: DocumentService,
    private characterHighlightService: CharacterHighlightService,
    private chapterStateService: ChapterStateService,
    private aiService: AiService,
    private cdr: ChangeDetectorRef,
    private el: ElementRef,
    private zone: NgZone
  ) {
    this.cursorSaveSubject.pipe(
      debounceTime(500)
    ).subscribe(() => {
      this.saveCurrentCursorState();
    });
  }

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

          // CRITICAL: specific check to prevent overwriting local DOM state while typing
          // If we are locally typing, we keep the current 'sentences' array reference
          // but valid updates from backend (processed by service) are merged via
          // handleSentenceUpdated logic usually, but here we just avoid array replacement.
          if (!this.isLocalTyping) {
            this.sentences = doc.sentences;
            // Only initialize chapter states if not typing locally
            this.initializeChapterStates();
          } else {
          }

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
        if (emoji !== this.hoveredEmoji) {
          // Only log when actually changing
          console.log('👁️ [TEXT-VIEWER] Hovered emoji changed to:', emoji);
        }
        this.hoveredEmoji = emoji;
        this.cdr.markForCheck();
      });

    // Subscribe to highlight color
    this.characterHighlightService.highlightColor$
      .pipe(takeUntil(this.destroy$))
      .subscribe(color => {
        this.highlightColor = color;
      });

    // Subscribe to sentence-specific highlighting
    this.characterHighlightService.highlightedSentenceId$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentenceId => {
        this.highlightedSentenceId = sentenceId;
        this.cdr.markForCheck();
      });

    // Subscribe to sentence highlight color
    this.characterHighlightService.sentenceHighlightColor$
      .pipe(takeUntil(this.destroy$))
      .subscribe(color => {
        this.sentenceHighlightColor = color;
        this.cdr.markForCheck();
      });
  }

  ngAfterViewInit(): void {
    // Set up passive scroll listeners for better performance
    // Use a small delay to ensure ViewChild elements are available
    setTimeout(() => {
      this.setupScrollListeners();
    }, 100);
  }
  get totalWords(): number {
    if (!this.chapters) return 0;

    return this.chapters.reduce((sum, chapter) => {
      // Wir holen die Sätze des Kapitels über deine existierende Methode
      const sentences = this.getChapterSentences(chapter.id) || [];
      // Wir fügen alle Sätze zu einem langen Text zusammen
      const chapterText = sentences.map(s => s.text).join(' ');

      // Zähle Wörter (filtert leere Strings raus)
      const words = chapterText.trim().split(/\s+/).filter(w => w.length > 0);
      return sum + words.length;
    }, 0);
  }

  /** Berechnet die Gesamtzahl aller Sätze im Dokument */
  get totalSentences(): number {
    if (!this.chapters) return 0;

    return this.chapters.reduce((sum, chapter) => {
      const chapterSentences = this.getChapterSentences(chapter.id);
      return sum + (chapterSentences ? chapterSentences.length : 0);
    }, 0);
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

      // Sync history if content has changed externally (not from local typing)
      if (!this.isLocalTyping) {
        this.chapterStateService.syncHistory(chapter.id, chapterContent);
      }
    }
  }

  private triggerGlobalUndoSnapshot(sentenceId: string, newText: string): void {
    if (!this.currentDocument) return;

    const updatedFullContent = this.sentences
      .map(s => s.id === sentenceId ? newText : s.text)
      .join(' ');
    this.documentService.updateContentSilent(this.currentDocument.id, updatedFullContent);

  }



  /**
   * Save current cursor state for active chapter
   * NEW: Ob AI-Highlight für diesen Satz angezeigt werden soll.
   * Wenn User einmal tippt -> Highlight wird eingefroren und verschwindet.
   */
  shouldHighlightAi(sentence: Sentence): boolean {
    if (!this.showAiHighlight) return false;
    return this.isAiGenerated(sentence);
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
        // sentenceElement IS the contenteditable element
        const textNode = sentenceElement;
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

          // sentenceElement IS the contenteditable element
          const textElement = sentenceElement as HTMLElement;
          if (textElement) {
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

  onSentenceHover(sentence: Sentence): void {
    this.hoveredSentence = sentence;
  }

  onSentenceLeave(): void {
    this.hoveredSentence = null;
  }

  onSentenceMouseEnter(sentence: Sentence): void {
    this.hoveredSentenceForTooltip = sentence.id;
  }

  onSentenceMouseLeave(): void {
    this.hoveredSentenceForTooltip = null;
  }

  shouldShowEmojiTooltip(sentence: Sentence): boolean {
    return this.hoveredSentenceForTooltip === sentence.id && sentence.emojis && sentence.emojis.length > 0;
  }

  generateEmojisForSentence(sentence: Sentence): void {
    if (!sentence.text || sentence.text.trim().length === 0) {
      return;
    }

    this.generatingSentenceId = sentence.id;

    this.aiService.generateEmojisFromText(sentence.text).subscribe({
      next: (emojis) => {
        // Update sentence with generated emojis
        sentence.emojis = emojis;
        this.documentService.updateSentenceEmojis(sentence.id, emojis);
        this.generatingSentenceId = null;
        this.hoveredSentence = null; // Hide toolbar after generation
      },
      error: (err) => {
        console.error('Failed to generate emojis:', err);
        this.generatingSentenceId = null;
        // Could show error notification here
      }
    });
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
          this.isLocalTyping = true;
          try {
            this.documentService.updateSentenceText(sentence.id, trimmedText);
          } finally {
            this.isLocalTyping = false;
          }
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
        this.isLocalTyping = true;
        try {
          this.documentService.updateSentenceText(sentence.id, trimmedNewText);
        } finally {
          this.isLocalTyping = false;
        }

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
   * Extract only the relevant text content from the chapter container,
   * ignoring UI artifacts like emoji tooltips and delete buttons.
   */
  private extractCleanText(container: HTMLElement): string {
    let text = '';

    // Walk the DOM tree
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
      {
        acceptNode: (node: Node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as HTMLElement;
            // Ignore UI artifacts
            if (el.classList.contains('emoji-tooltip') ||
              el.classList.contains('delete-ai-btn')) {
              return NodeFilter.FILTER_REJECT;
            }
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let node: Node | null;
    while (node = walker.nextNode()) {
      if (node.nodeType === Node.TEXT_NODE) {
        text += node.textContent;
      }
    }

    // Normalize spaces (replace non-breaking spaces with normal spaces)
    return text.replace(/\u00A0/g, ' ');
  }

  /**
   * Handle input on the full chapter container
   * This enables "Select All" + Delete functionality
   */
  onChapterContentInput(event: Event, chapterId: string): void {
    const target = event.target as HTMLElement;
    const fullText = this.extractCleanText(target); // Use clean text extraction

    // Set active chapter
    if (this.activeChapterId !== chapterId) {
      this.chapterStateService.setActiveChapter(chapterId);
    }

    this.debouncedSaveCursor();

    // Check if empty (user deleted everything)
    if (!fullText.trim()) {
      const currentDoc = this.documentService.getCurrentDocument();
      if (currentDoc) {
        this.chapterStateService.addHistoryEntry(chapterId, '');
        this.documentService.updateChapterContent(currentDoc.id, chapterId, '');
        return;
      }
    }

    // Identify which sentence is being modified to keep local updates fast
    // We try to find the sentence element from the selection
    const selection = window.getSelection();
    let limitLocalUpdate = false;

    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      let node: Node | null = range.commonAncestorContainer;
      while (node && node !== target) {
        if (node instanceof HTMLElement && node.hasAttribute('data-sentence-id')) {
          const sentenceId = node.getAttribute('data-sentence-id');
          const sentence = this.sentences.find(s => s.id === sentenceId);
          if (sentence) {
            // Found the sentence being edited!
            // We can do a local update for better performance if it's just typing
            limitLocalUpdate = true;

            // Capture cursor offset relative to the text node
            const cursorOffset = range.endOffset;
            // Capture the sentence ID to locate it after re-render
            const targetSentenceId = sentenceId;

            // Extract text for this specific sentence from the DOM
            const newSentenceText = node.innerText;
            const oldText = sentence.text;

            // Update local object reference immediately to prevent drift
            // We MUST update the model, otherwise Angular will fight the DOM
            sentence.text = newSentenceText;

            // Logic from onSentenceInput:
            const lastChar = newSentenceText.trim().slice(-1);
            const endsWithPunctuation = /[.!?]/.test(lastChar);
            const oldEndsWithPunctuation = /[.!?]/.test(oldText.trim().slice(-1));
            const justCompletedSentence = endsWithPunctuation && !oldEndsWithPunctuation;

            // Also check for major length diff which implies paste/delete
            const isMajorChange = Math.abs(newSentenceText.length - oldText.length) > 10;

            if (justCompletedSentence || isMajorChange) {
              // Trigger full update to split or handle bulk edit
              limitLocalUpdate = false;
            } else {
              // Just update local model
              this.isLocalTyping = true;
              try {
                this.documentService.updateSentenceText(sentence.id, newSentenceText);
              } finally {
                this.isLocalTyping = false;
              }

              // Restore cursor position robustly
              setTimeout(() => {
                const sel = window.getSelection();
                if (!sel) return;

                // Find the sentence element again (Angular might have re-rendered it)
                const sentenceEl = document.querySelector(`span[data-sentence-id="${targetSentenceId}"] .sentence-text`);

                if (sentenceEl) {
                  // Find the text node within the sentence element
                  let targetNode: Node | null = sentenceEl.firstChild;

                  // Handle case where text node is nested or missing
                  if (!targetNode && newSentenceText.length > 0) {
                    // Weird case, maybe empty?
                  } else if (targetNode) {
                    // Ensure we are inside a text node
                    if (targetNode.nodeType !== Node.TEXT_NODE) {
                      // Try to find the first text node child
                      const iterator = document.createNodeIterator(sentenceEl, NodeFilter.SHOW_TEXT);
                      targetNode = iterator.nextNode();
                    }
                  }

                  if (targetNode) {
                    try {
                      // Clamp offset to length
                      const validOffset = Math.min(cursorOffset, targetNode.textContent?.length || 0);

                      const newRange = document.createRange();
                      newRange.setStart(targetNode, validOffset);
                      newRange.collapse(true);
                      sel.removeAllRanges();
                      sel.addRange(newRange);
                    } catch (e) {
                      console.warn('Failed to restore cursor', e);
                    }
                  }
                }
              }, 0);

              // Set a timer to sync full chapter eventually to be safe
              if (this.sentenceUpdateTimer) clearTimeout(this.sentenceUpdateTimer);
              this.sentenceUpdateTimer = setTimeout(() => {
                // Construct clean text from model instead of DOM to avoid duplications
                const chapterSentences = this.getChapterSentences(chapterId);
                const cleanText = chapterSentences.map(s => s.text).join(' ').trim();
                this.syncFullChapterContent(chapterId, cleanText);
              }, 3000);
            }
          }
          break;
        }
        node = node.parentNode;
      }
    }

    if (!limitLocalUpdate) {
      // Major change (deletion across sentences, or split)
      // Debounce full update - faster now (300ms) for better responsiveness
      if (this.sentenceUpdateTimer) clearTimeout(this.sentenceUpdateTimer);
      this.sentenceUpdateTimer = setTimeout(() => {
        this.syncFullChapterContent(chapterId, fullText);
      }, 300);
    }
  }

  onChapterContentBlur(event: Event, chapterId: string): void {
    const target = event.target as HTMLElement;
    this.saveCurrentCursorState();
    // Ensure final consistency
    this.syncFullChapterContent(chapterId, this.extractCleanText(target));
  }

  private syncFullChapterContent(chapterId: string, fullText: string): void {
    const currentDoc = this.documentService.getCurrentDocument();
    if (currentDoc) {
      this.chapterStateService.addHistoryEntry(chapterId, fullText);
      this.documentService.updateChapterContent(currentDoc.id, chapterId, fullText);
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

  toggleAddMenu(): void {
    this.showAddMenu = !this.showAddMenu;
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event): void {
    const target = event.target as HTMLElement;
    // Close add menu if clicking outside
    if (this.showAddMenu && !target.closest('.add-dropdown-container')) {
      this.showAddMenu = false;
    }
  }

  isAiGenerated(sentence: Sentence): boolean {
    if (!sentence) return false;
    // Check both standard and raw property names to be safe
    return !!sentence.isAiGenerated || !!(sentence as any).is_ai_generated;
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
      // This emoji IS a character - use character's word phrases AND character name/aliases
      for (const character of charactersWithEmoji) {
        // ALWAYS add character name first (this ensures "dragon" is highlighted for dragon character)
        phrases.push(character.name);

        // Add aliases
        if (character.aliases && character.aliases.length > 0) {
          phrases.push(...character.aliases);
        }

        // Add character's stored word phrases (from when it was created)
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

    // Remove duplicates, empty strings, and sort by length (longest first to avoid partial matches)
    phrases = [...new Set(phrases.map(p => p.trim()).filter(p => p.length > 0))]
      .sort((a, b) => b.length - a.length);

    // Find all phrase occurrences in the text using word boundaries
    const segments: Array<{ text: string, isHighlighted: boolean }> = [];
    const matches: Array<{ start: number, end: number, phrase: string }> = [];

    for (const phrase of phrases) {
      // Escape special regex characters
      const escapedPhrase = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Use word boundary regex to avoid false matches (e.g., "hero" shouldn't match "heroic")
      const regex = new RegExp(`\\b${escapedPhrase}\\b`, 'gi');
      let match;
      // Reset regex lastIndex to ensure we find all matches
      regex.lastIndex = 0;
      while ((match = regex.exec(sentence.text)) !== null) {
        matches.push({
          start: match.index,
          end: match.index + match[0].length,
          phrase: match[0]
        });
        // Prevent infinite loop on zero-length matches
        if (match.index === regex.lastIndex) {
          regex.lastIndex++;
        }
      }
    }

    // Sort matches by position and remove overlaps (keep longest matches)
    matches.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
    const filteredMatches: Array<{ start: number, end: number }> = [];
    for (const match of matches) {
      // Check if this match truly overlaps with any existing match
      const overlaps = filteredMatches.some(existing => {
        // Two matches overlap if one starts before the other ends and vice versa
        return (match.start < existing.end && match.end > existing.start);
      });
      if (!overlaps) {
        filteredMatches.push(match);
      }
    }

    // Build segments
    if (filteredMatches.length === 0) {
      return [{ text: sentence.text, isHighlighted: false }];
    }

    // Sort final matches by position
    filteredMatches.sort((a, b) => a.start - b.start);

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
  // Cache for chapter sentences to prevent ngFor thrashing
  private chapterSentencesCache = new Map<string, Sentence[]>();
  private lastSentencesRef: Sentence[] | null = null;

  getChapterSentences(chapterId: string): Sentence[] {
    // If the sentences array reference has changed, clear the cache
    if (this.sentences !== this.lastSentencesRef) {
      this.chapterSentencesCache.clear();
      this.lastSentencesRef = this.sentences;
    }

    if (!this.chapterSentencesCache.has(chapterId)) {
      const filtered = this.sentences.filter(s => s.chapterId === chapterId);
      this.chapterSentencesCache.set(chapterId, filtered);
    }

    return this.chapterSentencesCache.get(chapterId) || [];
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
  addSection(): void {
    // Dispatch event to show section creation form in sidebar
    window.dispatchEvent(new CustomEvent('showSectionForm'));
  }

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

    // Extract existing number from the original title to preserve it
    const existingNumberMatch = chapter.title.match(/^(\d+)\s/);
    let newTitle: string;

    if (existingNumberMatch) {
      // Preserve the existing chapter number
      newTitle = `${existingNumberMatch[1]} ${this.editingChapterTitle.trim()}`;
    } else {
      // No existing number, just use the title as-is
      newTitle = this.editingChapterTitle.trim();
    }

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
   * Start editing chapter emoji
   */
  startEditChapterEmoji(chapter: Chapter): void {
    this.editingChapterEmojiId = chapter.id;
    this.editingChapterEmoji = chapter.emoji || '';
  }

  /**
   * Cancel editing chapter emoji
   */
  cancelEditChapterEmoji(): void {
    this.editingChapterEmojiId = null;
    this.editingChapterEmoji = '';
  }

  /**
   * Save chapter emoji
   */
  saveChapterEmoji(chapter: Chapter): void {
    if (!this.currentDocument) {
      this.cancelEditChapterEmoji();
      return;
    }

    const newEmoji = this.editingChapterEmoji.trim() || undefined;

    this.documentService.updateChapter(
      this.currentDocument.id,
      chapter.id,
      chapter.title,
      chapter.type,
      newEmoji
    ).subscribe({
      next: () => {
        this.cancelEditChapterEmoji();
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error updating chapter emoji:', err);
        alert('Failed to update chapter emoji. Please try again.');
        this.cancelEditChapterEmoji();
      }
    });
  }

  /**
   * Select emoji for editing (auto-saves)
   */
  selectEmojiForEditing(emoji: string, chapter: Chapter): void {
    const newEmoji = this.editingChapterEmoji === emoji ? '' : emoji;
    this.editingChapterEmoji = newEmoji;
    // Auto-save immediately
    if (this.currentDocument) {
      this.documentService.updateChapter(
        this.currentDocument.id,
        chapter.id,
        chapter.title,
        chapter.type,
        newEmoji || undefined
      ).subscribe({
        next: () => {
          this.cancelEditChapterEmoji();
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error('Error updating chapter emoji:', err);
        }
      });
    }
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

  getAiCategoryClass(sentence: Sentence): string {
    if (!sentence.isAiGenerated || !sentence.aiCategory) return '';
    return `ai-category-${sentence.aiCategory}`;
  }

  /**
   * Handle placeholder click - focus the editor
   */
  onPlaceholderClick(chapterId: string | null): void {
    // Placeholder is already contenteditable, so clicking will focus it
  }
  /**
   * Delete an AI-generated sentence
   */
  deleteAiSentence(sentence: Sentence, event: Event): void {
    event.stopPropagation();
    event.preventDefault(); // Prevent focus loss or other side effects

    if (!this.currentDocument) return;

    if (confirm('Delete this AI-generated sentence?')) {
      if (sentence.chapterId) {
        // Handle sentence in a chapter
        const chapterSentences = this.getChapterSentences(sentence.chapterId)
          .sort((a, b) => a.index - b.index);

        // Filter out this sentence
        const updatedSentences = chapterSentences.filter(s => s.id !== sentence.id);

        // Reconstruct text
        const newChapterText = updatedSentences.map(s => s.text).join(' ').trim();

        // Push update
        this.chapterStateService.addHistoryEntry(sentence.chapterId, newChapterText);
        this.documentService.updateChapterContent(this.currentDocument.id, sentence.chapterId, newChapterText);
      } else {
        // Handle unassigned sentence or no-chapter mode
        // Reconstruct full document content excluding this sentence
        const sortedSentences = [...this.sentences].sort((a, b) => a.index - b.index);
        const updatedSentences = sortedSentences.filter(s => s.id !== sentence.id);
        const newFullContent = updatedSentences.map(s => s.text).join(' ').trim();

        this.documentService.updateDocumentContent(this.currentDocument.id, newFullContent);
      }
    }
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
   * For "All Chapters" view: Extends line numbers to cover full height and indents text
   * For single chapter view: Aligns line numbers with flowing text only
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

      // Get computed styles for accurate line height calculation
      const computedStyle = window.getComputedStyle(textContentEl);
      const lineHeight = parseFloat(computedStyle.lineHeight) || parseFloat(computedStyle.fontSize) * 2;

      // Check if we're in "All Chapters" view (selectedChapterId is null and we have multiple chapters)
      const isAllChaptersView = !this.selectedChapterId && this.chapters.length > 1;

      if (isAllChaptersView) {
        // NEW LOGIC FOR "ALL CHAPTERS" VIEW:
        // Extend line numbers to cover full height (including chapter titles)
        // Indent text content to align with line numbers

        // Get the total scrollable height of the text content (includes everything)
        const textScrollHeight = textContentEl.scrollHeight;
        const textPaddingTop = parseFloat(getComputedStyle(textContentEl).paddingTop) || 0;
        const textPaddingBottom = parseFloat(getComputedStyle(textContentEl).paddingBottom) || 0;

        // Calculate total content height (including chapter titles and spacing)
        const totalContentHeight = textScrollHeight - textPaddingTop - textPaddingBottom;

        // Calculate number of lines to cover the entire height
        const numberOfLines = Math.max(1, Math.ceil(totalContentHeight / lineHeight));

        // Generate line numbers array covering full height
        this.lineNumbers = Array.from({ length: numberOfLines }, (_, i) => i + 1);

        if (lineNumbersEl && textContentEl) {
          // No padding-top offset - line numbers start from the very top
          lineNumbersEl.style.paddingTop = '0px';
          lineNumbersEl.style.paddingBottom = `${textPaddingBottom}px`;

          // Add a class to indicate "All Chapters" view for styling
          lineNumbersEl.classList.add('all-chapters-view');
          textContentEl.classList.add('all-chapters-view');
        }
      } else {
        // ORIGINAL LOGIC FOR SINGLE CHAPTER VIEW:
        // Align line numbers with flowing text only (excludes chapter titles)

        // Remove "All Chapters" view classes if present
        if (lineNumbersEl) {
          lineNumbersEl.classList.remove('all-chapters-view');
        }
        if (textContentEl) {
          textContentEl.classList.remove('all-chapters-view');
        }

        // Get all chapter-sentences containers (excludes chapter titles)
        const chapterSentencesContainers = textContentEl.querySelectorAll('.chapter-sentences');

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
                  const titleElement = titleWrapper as HTMLElement;
                  // Get the actual rendered height including margins and padding
                  const titleRect = titleElement.getBoundingClientRect();
                  const titleStyle = window.getComputedStyle(titleElement);
                  const titleMarginBottom = parseFloat(titleStyle.marginBottom) || 0;
                  const titlePaddingTop = parseFloat(titleStyle.paddingTop) || 0;
                  // Include padding-top in the offset calculation to account for the added space
                  firstTextLineOffset = titleRect.height + titleMarginBottom + titlePaddingTop;
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

        // Calculate number of lines based on actual text height (excluding chapter titles)
        const textScrollHeight = textContentEl.scrollHeight;
        const textPaddingTop = parseFloat(getComputedStyle(textContentEl).paddingTop) || 0;
        const textPaddingBottom = parseFloat(getComputedStyle(textContentEl).paddingBottom) || 0;

        // Calculate the actual content height (excluding padding)
        const actualContentHeight = textScrollHeight - textPaddingTop - textPaddingBottom;

        // Calculate number of lines - each line is exactly lineHeight tall
        const numberOfLines = Math.max(1, Math.ceil(actualContentHeight / lineHeight));

        // Generate line numbers array
        this.lineNumbers = Array.from({ length: numberOfLines }, (_, i) => i + 1);

        // Ensure line numbers container has the same total height as text content
        if (lineNumbersEl && textContentEl) {
          // Set padding-top to match any offset in text content (e.g., chapter titles)
          if (firstTextLineOffset > 0) {
            lineNumbersEl.style.paddingTop = `${firstTextLineOffset}px`;
          } else {
            lineNumbersEl.style.paddingTop = '0px';
          }

          // Ensure padding-bottom matches exactly
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
      }

      this.cdr.markForCheck();
    }, 150); // Debounce for 150ms to allow DOM to settle
  }

  /**
   * Request AI title suggestion for a chapter
   */
  requestTitleSuggestion(chapter: Chapter): void {
    if (!this.currentDocument || this.titleSuggestionLoading) return;

    this.suggestingTitleForChapterId = chapter.id;
    this.titleSuggestionLoading = true;
    this.aiTitleSuggestion = null;

    this.documentService.suggestChapterTitle(this.currentDocument.id, chapter.id).subscribe({
      next: (response) => {
        this.aiTitleSuggestion = response.suggested_title;
        this.titleSuggestionLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error getting title suggestion:', err);
        this.titleSuggestionLoading = false;
        this.suggestingTitleForChapterId = null;
        alert('Failed to generate title suggestion. Please try again.');
      }
    });
  }

  /**
   * Apply AI-suggested title
   */
  applyTitleSuggestion(chapter: Chapter): void {
    if (!this.currentDocument || !this.aiTitleSuggestion) return;

    // Extract current chapter number if it's a numbered chapter
    let newTitle: string;
    if (chapter.type === 'chapter') {
      // Extract current number from title
      const chapterMatch = chapter.title.match(/Chapter\s+(\d+)/i);
      const numMatch = chapter.title.match(/^(\d+)\s+/);

      let chapterNum: string;
      if (chapterMatch) {
        chapterNum = chapterMatch[1];
      } else if (numMatch) {
        chapterNum = numMatch[1];
      } else {
        // Fallback: use index + 1
        const numberedChapters = this.chapters.filter(ch => ch.type === 'chapter');
        const chapterIndex = numberedChapters.findIndex(ch => ch.id === chapter.id);
        chapterNum = (chapterIndex + 1).toString().padStart(2, '0');
      }

      const paddedNum = parseInt(chapterNum, 10).toString().padStart(2, '0');
      newTitle = `${paddedNum} ${this.aiTitleSuggestion}`;
    } else {
      // For special sections, use suggestion as-is
      newTitle = this.aiTitleSuggestion;
    }

    this.documentService.updateChapter(
      this.currentDocument.id,
      chapter.id,
      newTitle,
      chapter.type,
      chapter.emoji || undefined
    ).subscribe({
      next: () => {
        this.suggestingTitleForChapterId = null;
        this.aiTitleSuggestion = null;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error applying title suggestion:', err);
        alert('Failed to apply title suggestion. Please try again.');
      }
    });
  }

  /**
   * Cancel title suggestion
   */
  cancelTitleSuggestion(): void {
    this.suggestingTitleForChapterId = null;
    this.aiTitleSuggestion = null;
    this.titleSuggestionLoading = false;
  }

  /**
   * Request AI emoji suggestion for a chapter
   */
  requestEmojiSuggestion(chapter: Chapter): void {
    if (!this.currentDocument || this.emojiSuggestionLoading) return;

    this.suggestingEmojiForChapterId = chapter.id;
    this.emojiSuggestionLoading = true;
    this.aiEmojiSuggestion = null;

    this.documentService.suggestChapterEmoji(this.currentDocument.id, chapter.id).subscribe({
      next: (response) => {
        this.aiEmojiSuggestion = response.suggested_emoji;
        this.emojiSuggestionLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error getting emoji suggestion:', err);
        this.emojiSuggestionLoading = false;
        this.suggestingEmojiForChapterId = null;
        alert('Failed to generate emoji suggestion. Please try again.');
      }
    });
  }

  /**
   * Apply AI-suggested emoji
   */
  applyEmojiSuggestion(chapter: Chapter): void {
    if (!this.currentDocument || !this.aiEmojiSuggestion) return;

    this.editingChapterEmoji = this.aiEmojiSuggestion;
    this.saveChapterEmoji(chapter);
    this.suggestingEmojiForChapterId = null;
    this.aiEmojiSuggestion = null;
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

  /**
   * Get chapter display title for workspace dropdown (shows "Chapter 1", "Chapter 2", etc.)
   */
  getChapterDisplayTitle(chapter: Chapter): string {
    // Only chapters should have numbers - special sections should not
    if (chapter.type === 'chapter') {
      // For workspace dropdown, show just "Chapter 1", "Chapter 2", etc. (without title)
      // Extract chapter number from title
      const chapterMatch = chapter.title.match(/Chapter\s+(\d+)/i);
      if (chapterMatch) {
        return `Chapter ${chapterMatch[1]}`;
      }
      // Handle format like "01 Title" or "1 Title" - extract number
      const numMatch = chapter.title.match(/^(\d+)\s+/);
      if (numMatch) {
        const num = parseInt(numMatch[1], 10);
        return `Chapter ${num}`;
      }
      // Fallback: use index + 1
      const numberedChapters = this.chapters.filter(ch => ch.type === 'chapter');
      const chapterIndex = numberedChapters.findIndex(ch => ch.id === chapter.id);
      return `Chapter ${chapterIndex + 1}`;
    } else {
      // For special sections (prologue, epilogue, afterword, etc.) and custom sections, remove any numbers
      const cleanedTitle = chapter.title.replace(/^\d+\s+/, '').trim();
      return cleanedTitle || chapter.title;
    }
  }

  /**
   * Get chapter title for display in text editor (shows "01 Slay" format)
   */
  getChapterTitleDisplay(chapter: Chapter): string {
    // Only chapters should have numbers - special sections should not
    if (chapter.type === 'chapter') {
      // For numbered chapters, show the full title with number (e.g., "01 Slay")
      // Handle formats like "Chapter 1: Title" -> convert to "01 Title"
      const chapterMatch = chapter.title.match(/Chapter\s+(\d+)\s*:?\s*(.*)$/i);
      if (chapterMatch) {
        const num = parseInt(chapterMatch[1], 10);
        const titlePart = chapterMatch[2]?.trim() || '';
        const paddedNum = num.toString().padStart(2, '0');
        if (titlePart) {
          return `${paddedNum} ${titlePart}`;
        } else {
          return paddedNum;
        }
      }
      // Handle format like "01 Title" or "1 Title" - ensure padding
      const numMatch = chapter.title.match(/^(\d+)\s+(.+)$/);
      if (numMatch) {
        const num = parseInt(numMatch[1], 10);
        const titlePart = numMatch[2].trim();
        const paddedNum = num.toString().padStart(2, '0');
        return `${paddedNum} ${titlePart}`;
      }
      // If it's just a number, pad it
      const justNum = chapter.title.match(/^(\d+)$/);
      if (justNum) {
        const num = parseInt(justNum[1], 10);
        return num.toString().padStart(2, '0');
      }
      return chapter.title;
    } else {
      // For special sections (prologue, epilogue, afterword, etc.) and custom sections, remove any numbers
      const cleanedTitle = chapter.title.replace(/^\d+\s+/, '').trim();
      return cleanedTitle || chapter.title;
    }
  }
}
