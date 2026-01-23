import {
  Component,
  OnInit,
  OnDestroy,
  Input, Output, EventEmitter,
  HostListener,
  ViewChild,
  ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { DocumentService } from '../../../core/services/document.service';
import { AiService } from '../../../core/services/ai.service';
import { CharacterFormService } from '../../../core/services/character-form.service';
import { CharacterHighlightService } from '../../../core/services/character-highlight.service';
import { ChapterStateService } from '../../../core/services/chapter-state.service';
import { Sentence, Chapter, DocumentDetail } from '../../../core/models/document.model';
import { CharacterManagerComponent } from '../character-manager/character-manager.component';

type Dimension = 'drama' | 'humor' | 'conflict' | 'mystery';

interface ChapterAnalysis {
  drama: number;
  humor: number;
  conflict: number;
  mystery: number;
  textHash?: string;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CharacterManagerComponent
  ],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit, OnDestroy {
  private _activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' = 'ai';

  // ===== INTENT PANEL STATE =====
  intentSummary: string | null = null;
  intentIdeas: string[] = [];
  intentPreview: string | null = null;
  intentLoading = false;
  textApplied = false;
  currentIntentDimension: Dimension | null = null;
  private sliderChangeSubject = new Subject<{ dimension: Dimension; current: number; baseline: number; requestId: number }>();
  private requestCounter = 0;
  private preserveSlidersOnNextAnalysis = false;

  // ===== BASELINE VALUES NACH AI-ANALYSE =====
  // baseline = AI analysis result (NOT user override)
  aiBaseline: Record<Dimension, number> = {
    drama: 65,
    humor: 40,
    conflict: 80,
    mystery: 30,
  };

  @Input()
  set activeTab(value: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc') {
    this._activeTab = value;
    if (value === 'analysis' && !this.isAnalyzing) {
      // Ensure we have the latest document state
      const doc = this.documentService.getCurrentDocument();
      if (doc) {
        this.currentDocument = doc;
        this.chapters = (doc.chapters || []).sort((a, b) => a.index - b.index);
      }

      // Default to Chapter 1
      if (this.chapters.length > 0) {
        this.selectedAnalysisChapterId = this.chapters[0].id;
      } else {
        this.selectedAnalysisChapterId = 'all';
      }

      setTimeout(() => this.analyzeDocument(), 100);
    }
  }

  get activeTab(): 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' {
    return this._activeTab;
  }
  @Output() switchTab = new EventEmitter<'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc'>();

  selectedSentence: Sentence | null = null;
  currentDocument: DocumentDetail | null = null;
  chapters: Chapter[] = [];
  emojiDictionary: any = null;  // Emoji dictionary data
  isGenerating = false;
  isGeneratingEmojisForAll = false;
  lastSuggestion: string | null = null;

  private destroy$ = new Subject<void>();

  // Enhanced emoji feature panels
  showWordMappingPanel = false;
  showCharacterPanel = false;
  showEmojiSetPanel = false;

  // Emoji management
  maxEmojis = 5;
  commonEmojis = [
    '😀', '😊', '😢', '😱', '😡', '😍', '🤔', '😴',
    '🎉', '🎨', '🎭', '🎪', '🎬', '📖', '✨', '🌟',
    '🌙', '☀️', '⛈️', '🌈', '🔥', '💧', '💔', '💖',
    '👑', '👻', '🦄', '🐉', '🧙‍♂️', '🧛‍♀️', '🧜‍♂️', '🏰'
  ];

  // ===== SPIDER CHART VALUES =====
  drama = 65;
  humor = 40;
  conflict = 80;
  mystery = 30;

  private readonly centerX = 100;
  private readonly centerY = 100;
  private readonly maxRadius = 80;

  @ViewChild('spiderSvg') spiderSvg?: ElementRef<SVGSVGElement>;
  draggingHandle: Dimension | null = null;


  isAnalyzing = false;
  lastAnalysisError: string | null = null;
  private lastAnalyzedDocumentId: string | null = null;
  private lastAnalyzedTextHash: string | null = null;
  selectedAnalysisChapterId: string | null = 'all';
  focusedChapterIndex = 0;
  chapterAnalyses: { [key: string]: ChapterAnalysis } = {};
  isAnalyzingAll = false;

  // ✅ NEW: track "committed" (Apply Text) state per chapter+hash
  private appliedStateByChapter: { [chapterId: string]: { textHash: string; applied: boolean } } = {};

  constructor(
    public documentService: DocumentService,
    private aiService: AiService,
    private characterHighlightService: CharacterHighlightService,
    private characterFormService: CharacterFormService,
    private chapterStateService: ChapterStateService
  ) { }

  private computeTextHash(text: string): string {
    const t = text || '';
    return `${t.length}_${t.substring(0, 50)}`;
  }

  // ========== INIT ==========
  ngOnInit(): void {
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => this.selectedSentence = sentence);

    // Load emoji dictionary when document changes
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        if (doc) {
          this.currentDocument = doc;
          this.chapters = (doc.chapters || []).sort((a, b) => a.index - b.index);
          this.loadEmojiDictionary(doc.id);
        }
      });

    this.documentService.currentDocument$
      .pipe(
        takeUntil(this.destroy$),
        debounceTime(1000), // Reduced from 2000ms for more responsive updates
        distinctUntilChanged((prev, curr) => {
          if (!prev || !curr) return prev === curr;
          // Compare only active chapter's content
          const activeChapterId = this.chapterStateService.getActiveChapterId();
          // If we are analyzing a specific chapter, we should compare THAT chapter's content
          const targetChapterId = this.selectedAnalysisChapterId === 'all' ? activeChapterId : this.selectedAnalysisChapterId;

          if (targetChapterId) {
            const prevActive = prev.sentences.filter(s => s.chapterId === targetChapterId).map(s => s.text).join(' ');
            const currActive = curr.sentences.filter(s => s.chapterId === targetChapterId).map(s => s.text).join(' ');
            return prevActive === currActive;
          }
          // Fallback: compare all content within first 500 chars (optimization) or full text
          return prev.sentences.map(s => s.text).join(' ') ===
            curr.sentences.map(s => s.text).join(' ');
        })
      )
      .subscribe(doc => {
        if (doc && this.activeTab === 'analysis' && !this.isAnalyzing) {
          if (this.chapters.length === 1) {
            // If exactly one chapter, force that chapter view
            this.selectedAnalysisChapterId = this.chapters[0].id;
          } else {
            // If 0 chapters (new doc) or > 1 chapters, default to 'all' (combined view)
            // Only set to activeChapterId if we specifically want to track the active one,
            // but user requested "entire story" as default view entering functionality.
            if (this.selectedAnalysisChapterId !== 'all' && !this.chapters.find(c => c.id === this.selectedAnalysisChapterId)) {
              this.selectedAnalysisChapterId = 'all';
            }
          }


          let currentText: string;
          const targetChapterId = this.selectedAnalysisChapterId === 'all' ? null : this.selectedAnalysisChapterId;

          if (targetChapterId) {
            const activeChapterSentences = doc.sentences.filter(s => s.chapterId === targetChapterId);
            currentText = activeChapterSentences.map(s => s.text).join(' ').trim();
          } else {
            currentText = doc.sentences.map(s => s.text).join(' ').trim();
          }

          if (currentText) {
            const textHash = this.computeTextHash(currentText);
            if (textHash !== this.lastAnalyzedTextHash) {
              // this.analyzeDocument() handles the update
              this.analyzeDocument();
            }
          }
        }
      });

    // ✅ Slider changes: DO NOT persist. Only fetch intent suggestions.
    this.sliderChangeSubject
      .pipe(
        takeUntil(this.destroy$),
        debounceTime(500)
        // REMOVED distinctUntilChanged - we want a NEW request every time the slider moves
      )
      .subscribe(({ dimension, current, baseline }) => {
        this.fetchIntentSuggestions(dimension, current, baseline);
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadEmojiDictionary(documentId: string): void {
    this.documentService.getEmojiDictionary(documentId).subscribe({
      next: (dictionary) => {
        this.emojiDictionary = dictionary;
      },
      error: (err) => console.error('Error loading emoji dictionary:', err)
    });
  }

  onEmojiDictionaryHover(entry: any): void {
    // Highlight all sentences containing this emoji
    console.log('🖱️ [SIDEBAR] Hovering emoji:', entry.emoji, 'color:', entry.color);
    this.characterHighlightService.setHoveredEmoji(entry.emoji, entry.color);
  }

  onEmojiDictionaryLeave(): void {
    this.characterHighlightService.clearHover();
  }

  getCharacterEntries(): any[] {
    if (!this.emojiDictionary) return [];
    return this.emojiDictionary.entries.filter((e: any) => e.characterId !== null);
  }

  getRecurringEntries(): any[] {
    if (!this.emojiDictionary) return [];
    return this.emojiDictionary.entries.filter((e: any) => e.characterId === null);
  }

  getEmojiWordPhrases(emoji: string): string[] {
    // Collect all word phrases for this emoji from all sentences
    const doc = this.documentService.getCurrentDocument();
    if (!doc) return [];

    const phrasesSet = new Set<string>();

    for (const sentence of doc.sentences) {
      if (sentence.emojiMappings && emoji in sentence.emojiMappings) {
        const phrases = sentence.emojiMappings[emoji];
        if (Array.isArray(phrases)) {
          phrases.forEach(p => phrasesSet.add(p));
        }
      }
    }

    return Array.from(phrasesSet);
  }

  // Drag and drop to merge emojis
  private draggedEntry: any = null;

  onDragStart(event: DragEvent, entry: any): void {
    this.draggedEntry = entry;
    event.dataTransfer!.effectAllowed = 'move';
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.dataTransfer!.dropEffect = 'move';
  }

  onDrop(event: DragEvent, targetEntry: any): void {
    event.preventDefault();

    if (!this.draggedEntry || this.draggedEntry === targetEntry) {
      this.draggedEntry = null;
      return;
    }

    // Confirm merge
    const confirm = window.confirm(
      `Merge ${this.draggedEntry.emoji} into ${targetEntry.emoji}?\n\n` +
      `All ${this.draggedEntry.usageCount} uses of ${this.draggedEntry.emoji} will be replaced with ${targetEntry.emoji}.`
    );

    if (confirm) {
      this.mergeEmojis(this.draggedEntry.emoji, targetEntry.emoji);
    }

    this.draggedEntry = null;
  }

  mergeEmojis(sourceEmoji: string, targetEmoji: string): void {
    const currentDoc = this.documentService.getCurrentDocument();
    if (!currentDoc) return;

    // Call backend to merge emojis across all sentences
    this.documentService.mergeEmojis(currentDoc.id, sourceEmoji, targetEmoji).subscribe({
      next: () => this.loadEmojiDictionary(currentDoc.id),
      error: (err) => console.error('Error merging emojis:', err)
    });
  }

  promoteToCharacter(entry: any): void {
    // The character manager is already visible in the same tab (emojis)
    // Just trigger the character form with pre-filled data
    this.characterFormService.openCharacterForm({
      emoji: entry.emoji,
      suggestedName: this.inferCharacterName(entry.meaning),
      description: entry.meaning
    });
  }

  private inferCharacterName(meaning: string): string {
    // Try to extract a good default name from the meaning
    if (meaning.includes('Represents')) {
      return meaning.split('Represents')[1].split(':')[0].trim();
    }
    return 'New Character';
  }

  editCharacter(entry: any): void { }

  addEmoji(emoji: string): void {
    if (!this.selectedSentence) return;
    if (this.selectedSentence.emojis.length >= this.maxEmojis) return;

    const newEmojis = [...this.selectedSentence.emojis, emoji];
    this.documentService.updateSentenceEmojis(this.selectedSentence.id, newEmojis);
  }

  removeEmoji(index: number): void {
    if (!this.selectedSentence) return;

    const newEmojis = this.selectedSentence.emojis.filter((_, i) => i !== index);
    this.documentService.updateSentenceEmojis(this.selectedSentence.id, newEmojis);
  }

  canAddMore(): boolean {
    return this.selectedSentence ? this.selectedSentence.emojis.length < this.maxEmojis : false;
  }

  generateEmojis(): void {
    if (!this.selectedSentence) return;

    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    const activeChapterId = this.chapterStateService.getActiveChapterId();
    if (activeChapterId && this.selectedSentence.chapterId !== activeChapterId) return;

    this.isGenerating = true;

    this.aiService.generateEmojisFromText({
      documentId: doc.id,
      sentenceId: this.selectedSentence.id,
      text: this.selectedSentence.text
    }).subscribe({
      next: (response) => {
        // Only update if sentence still belongs to active chapter
        const updatedDoc = this.documentService.getCurrentDocument();
        if (updatedDoc) {
          const updatedSentence = updatedDoc.sentences.find(s => s.id === this.selectedSentence!.id);
          if (updatedSentence && (!activeChapterId || updatedSentence.chapterId === activeChapterId)) {
            this.documentService.updateSentenceEmojis(this.selectedSentence!.id, response.emojis);
          }
        }
        this.isGenerating = false;
      },
      error: (err) => {
        console.error('Error generating emojis:', err);
        this.isGenerating = false;
      }
    });
  }

  generateEmojisForAll(): void {
    const editableElements = document.querySelectorAll('[contenteditable="true"]');
    editableElements.forEach(el => {
      if (el instanceof HTMLElement) el.blur();
    });

    setTimeout(() => {
      const doc = this.documentService.getCurrentDocument();
      if (!doc || !doc.sentences || doc.sentences.length === 0) return;

      // CRITICAL: Only generate emojis for sentences in the active chapter
      const activeChapterId = this.chapterStateService.getActiveChapterId();
      const sentencesToProcess = activeChapterId
        ? doc.sentences.filter(s => s.chapterId === activeChapterId)
        : doc.sentences;

      if (sentencesToProcess.length === 0) return;

      this.isGenerating = true;
      let processedCount = 0;
      const totalSentences = sentencesToProcess.length;

      this.processEmojisForAllSentences(doc, sentencesToProcess, processedCount, totalSentences);
    }, 150);
  }

  private processEmojisForAllSentences(doc: any, sentences: Sentence[], processedCount: number, totalSentences: number): void {
    // Process each sentence one by one
    sentences.forEach((sentence: Sentence, index: number) => {
      this.aiService.generateEmojisFromText({
        documentId: doc.id,
        sentenceId: sentence.id,
        text: sentence.text
      }).subscribe({
        next: (response) => {
          // Only update if sentence still belongs to active chapter
          const activeChapterId = this.chapterStateService.getActiveChapterId();
          const updatedDoc = this.documentService.getCurrentDocument();
          if (updatedDoc) {
            const updatedSentence = updatedDoc.sentences.find(s => s.id === sentence.id);
            if (updatedSentence && (!activeChapterId || updatedSentence.chapterId === activeChapterId)) {
              this.documentService.updateSentenceEmojis(sentence.id, response.emojis);
            }
          }
          processedCount++;
          if (processedCount === totalSentences) this.isGenerating = false;
        },
        error: (err) => {
          console.error(`Error generating emojis for sentence ${index + 1}:`, err);
          processedCount++;
          if (processedCount === totalSentences) this.isGeneratingEmojisForAll = false;
        }
      });
    });
  }

  generateTextFromEmojis(): void {
    if (!this.selectedSentence || this.selectedSentence.emojis.length === 0) return;

    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    this.isGenerating = true;

    this.aiService.generateTextFromEmojis({
      documentId: doc.id,
      sentenceId: this.selectedSentence.id,
      emojis: this.selectedSentence.emojis
    }).subscribe({
      next: (response) => {
        this.lastSuggestion = response.suggestedText;
        this.isGenerating = false;
      },
      error: (err) => {
        console.error('Error generating text:', err);
        this.isGenerating = false;
      }
    });
  }

  applySuggestion(): void {
    if (!this.lastSuggestion || !this.selectedSentence) return;

    this.documentService.updateSentenceText(this.selectedSentence.id, this.lastSuggestion);
    this.documentService.setAiPrefixLen(this.selectedSentence.id, this.lastSuggestion.length);

    this.lastSuggestion = null;
  }

  // Enhanced emoji feature panel toggles
  showWordMappings(): void {
    this.showWordMappingPanel = !this.showWordMappingPanel;
    if (this.showWordMappingPanel) {
      this.showCharacterPanel = false;
      this.showEmojiSetPanel = false;
    }
  }

  showCharacters(): void {
    this.showCharacterPanel = !this.showCharacterPanel;
    if (this.showCharacterPanel) {
      this.showWordMappingPanel = false;
      this.showEmojiSetPanel = false;
    }
  }

  showEmojiSets(): void {
    this.showEmojiSetPanel = !this.showEmojiSetPanel;
    if (this.showEmojiSetPanel) {
      this.showWordMappingPanel = false;
      this.showCharacterPanel = false;
    }
  }

  private normalizeSentenceSpacing(text: string): string {
    return text
      .replace(/([.!?])(?=\S)/g, '$1 ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  applyPreviewText(): void {
    if (!this.intentPreview) return;
    if (this.textApplied) return;

    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    // CRITICAL: Only update the active chapter's content
    // CRITICAL: Only update the selected analysis chapter's content
    const targetChapterId = this.selectedAnalysisChapterId === 'all' ? null : this.selectedAnalysisChapterId;

    if (targetChapterId) {
      // Get selected chapter's sentences (sorted by index)
      const activeChapterSentences = doc.sentences
        .filter(s => s.chapterId === targetChapterId)
        .sort((a, b) => a.index - b.index);

      // Try to get cursor position for cursor-based insertion
      const cursorState = this.chapterStateService.getCursor(targetChapterId);
      let newChapterContent: string;

      if (cursorState && cursorState.sentenceId && cursorState.offset !== undefined) {
        // Insert at cursor position
        const cursorSentence = activeChapterSentences.find(s => s.id === cursorState.sentenceId);
        if (cursorSentence) {
          const sentenceText = cursorSentence.text;
          const beforeCursor = sentenceText.substring(0, cursorState.offset);
          const afterCursor = sentenceText.substring(cursorState.offset);

          // Insert the preview text at cursor position
          const updatedSentence = `${beforeCursor}${this.intentPreview}${afterCursor}`;

          // Reconstruct chapter content with updated sentence
          const chapterParts: string[] = [];
          for (const sentence of activeChapterSentences) {
            chapterParts.push(sentence.id === cursorState.sentenceId ? updatedSentence : sentence.text);
          }
          newChapterContent = chapterParts.join(' ').trim();
        } else {
          // Cursor sentence not found, fall back to appending
          const activeChapterContent = activeChapterSentences.map(s => s.text).join(' ').trim();
          newChapterContent = activeChapterContent
            ? `${activeChapterContent} ${this.intentPreview}`
            : this.intentPreview;
        }
      } else {
        // No cursor position available, append to end
        const activeChapterContent = activeChapterSentences.map(s => s.text).join(' ').trim();
        newChapterContent = activeChapterContent
          ? `${activeChapterContent} ${this.intentPreview}`
          : this.intentPreview;
      }

      // Update chapter history
      this.chapterStateService.addHistoryEntry(targetChapterId, newChapterContent);

      // CRITICAL: Update only active chapter's content, preserving others
      // Pass intentPreview as ai_suggestion_text to mark matching sentences as AI-generated
      // Pass currentIntentDimension as ai_suggestion_category to mark the category
      newChapterContent = this.normalizeSentenceSpacing(newChapterContent);
      // Force analysis refresh on next update
      this.lastAnalyzedTextHash = null;

      // Preserve slider values (no jump) on next analysis
      this.preserveSlidersOnNextAnalysis = true;

      // ✅ COMMIT ONLY HERE (Apply Text)
      const committedHash = this.computeTextHash(newChapterContent);

      this.chapterAnalyses[targetChapterId] = {
        drama: this.drama,
        humor: this.humor,
        conflict: this.conflict,
        mystery: this.mystery,
        textHash: committedHash
      };

      this.appliedStateByChapter[targetChapterId] = {
        textHash: committedHash,
        applied: true
      };

      this.documentService.updateChapterContent(
        doc.id,
        targetChapterId,
        newChapterContent,
        this.intentPreview,
        this.currentIntentDimension || undefined
      );
    } else {
      // Fallback: if no active chapter, update all content (backward compatibility)
      const currentContent = doc.sentences.map(s => s.text).join(' ').trim();
      const newContent = currentContent ? `${currentContent} ${this.intentPreview}` : this.intentPreview;

      // Force analysis refresh
      this.lastAnalyzedTextHash = null;
      this.preserveSlidersOnNextAnalysis = true;

      this.documentService.updateDocumentContent(
        doc.id,
        this.normalizeSentenceSpacing(newContent),
        this.intentPreview,
        this.currentIntentDimension || undefined
      );
    }

    // Mark as applied
    this.textApplied = true;
  }


  // ========== SPIDER SHAPE ==========
  private valueToPointXY(value: number, angleDeg: number) {
    const r = (value / 100) * this.maxRadius;
    const angleRad = (angleDeg * Math.PI) / 180;
    return {
      x: this.centerX + r * Math.cos(angleRad),
      y: this.centerY + r * Math.sin(angleRad)
    };
  }

  getSpiderPointsForValues(drama: number, humor: number, conflict: number, mystery: number): string {
    const dramaPoint = this.valueToPointXY(drama, -90);
    const humorPoint = this.valueToPointXY(humor, 0);
    const conflictPoint = this.valueToPointXY(conflict, 90);
    const mysteryPoint = this.valueToPointXY(mystery, 180);

    return [dramaPoint, humorPoint, conflictPoint, mysteryPoint]
      .map(p => `${p.x},${p.y}`).join(', ');
  }

  getChapterColor(index: number): string {
    const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
    return colors[index % colors.length];
  }

  get dramaPoint() { return this.valueToPointXY(this.drama, -90); }
  get humorPoint() { return this.valueToPointXY(this.humor, 0); }
  get conflictPoint() { return this.valueToPointXY(this.conflict, 90); }
  get mysteryPoint() { return this.valueToPointXY(this.mystery, 180); }

  get spiderPoints(): string {
    return [
      this.dramaPoint,
      this.humorPoint,
      this.conflictPoint,
      this.mysteryPoint
    ].map(p => `${p.x},${p.y}`).join(', ');
  }

  // ========== AI ANALYSIS ==========
  onAnalysisChapterChange(chapterId: string | null): void {
    // Optional neutral reset
    this.drama = 50;
    this.humor = 50;
    this.conflict = 50;
    this.mystery = 50;

    this.selectedAnalysisChapterId = chapterId;
    this.lastAnalyzedTextHash = null; // Force re-analysis by invalidating previous hash
    this.analyzeDocument();
  }

  // ========== AI ANALYSIS ==========
  analyzeDocument(): void {
    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    // Use selected chapter for analysis, or fallback to active chapter logic if 'all' is not explicitly handled yet
    // The previous logic was: activeChapterId (from state) or all.
    // New logic: Use selectedAnalysisChapterId. If 'all', use all.

    // We treat 'all' as null for the purpose of ID, but we strictly check for 'all' string from template
    const targetChapterId = this.selectedAnalysisChapterId === 'all' ? null : this.selectedAnalysisChapterId;

    let textToAnalyze: string;

    if (targetChapterId) {
      // Analyze only selected chapter
      const activeChapterSentences = doc.sentences.filter(s => s.chapterId === targetChapterId);
      textToAnalyze = activeChapterSentences.map(s => s.text).join(' ').trim();
    } else {
      // Analyze all content logic - TRIGGER BATCH ANALYSIS for "Entire Story" breakdown
      // Clear current analyses to force refresh visual
      // this.chapterAnalyses = {};
      this.analyzeAllChapters();
      return;
    }

    if (!textToAnalyze) return;

    const textHash = this.computeTextHash(textToAnalyze);

    // ✅ Only restore from cache if Apply Text was done for this exact textHash
    if (targetChapterId && this.chapterAnalyses[targetChapterId]) {
      const cached = this.chapterAnalyses[targetChapterId];
      const appliedState = this.appliedStateByChapter[targetChapterId];

      const isAppliedForThisText =
        appliedState?.applied === true &&
        appliedState.textHash === textHash &&
        cached.textHash === textHash;

      if (isAppliedForThisText) {
        this.drama = cached.drama;
        this.humor = cached.humor;
        this.conflict = cached.conflict;
        this.mystery = cached.mystery;
        return;
      }
    }

    this.isAnalyzing = true;
    this.lastAnalysisError = null;

    this.aiService.analyzeSpiderChart({
      documentId: doc.id,
      text: textToAnalyze
    }).subscribe({
      next: (response) => {
        // baseline = AI
        this.aiBaseline = {
          drama: response.drama,
          humor: response.humor,
          conflict: response.conflict,
          mystery: response.mystery
        };

        if (this.preserveSlidersOnNextAnalysis) {
          // Keep all sliders at their current positions (user intent)
          // We only update the baseline to reflect the new text reality
          // This prevents "jumping" values after applying an edit
          this.preserveSlidersOnNextAnalysis = false;
        } else {
          this.drama = response.drama;
          this.humor = response.humor;
          this.conflict = response.conflict;
          this.mystery = response.mystery;
        }

        this.lastAnalyzedTextHash = textHash;
        this.lastAnalyzedDocumentId = doc.id;

        // If text changed or not applied, mark as not applied for this hash
        if (targetChapterId) {
          const prev = this.appliedStateByChapter[targetChapterId];
          if (!prev || prev.textHash !== textHash) {
            this.appliedStateByChapter[targetChapterId] = { textHash, applied: false };
          }
        }

        this.isAnalyzing = false;
      },
      error: () => {
        this.lastAnalysisError = 'Failed to analyze text';
        this.isAnalyzing = false;
        this.preserveSlidersOnNextAnalysis = false;
      }
    });
  }

  analyzeAllChapters(): void {
    const doc = this.documentService.getCurrentDocument();
    if (!doc || !this.chapters.length) return;

    this.isAnalyzingAll = true;
    let completedCount = 0;

    this.chapters.forEach(chapter => {
      const chapterSentences = doc.sentences.filter(s => s.chapterId === chapter.id);
      const text = chapterSentences.map(s => s.text).join(' ').trim();

      if (!text) {
        // Skip empty chapters but count them as done
        completedCount++;
        if (completedCount === this.chapters.length) this.isAnalyzingAll = false;
        return;
      }

      this.aiService.analyzeSpiderChart({
        documentId: doc.id,
        text
      }).subscribe({
        next: (response) => {
          const textHash = this.computeTextHash(text);
          const existing = this.chapterAnalyses[chapter.id];
          const appliedState = this.appliedStateByChapter[chapter.id];

          const isAppliedForThisText =
            appliedState?.applied === true &&
            appliedState.textHash === textHash &&
            existing?.textHash === textHash;

          if (!isAppliedForThisText) {
            // Not applied -> show AI values in overview
            this.chapterAnalyses[chapter.id] = { ...response, textHash };
            this.appliedStateByChapter[chapter.id] = { textHash, applied: false };
          }

          completedCount++;
          if (completedCount === this.chapters.length) this.isAnalyzingAll = false;
        },
        error: () => {
          completedCount++;
          if (completedCount === this.chapters.length) this.isAnalyzingAll = false;
        }
      });
    });
  }

  // ========== DRAG HANDLE ==========
  startDrag(handle: Dimension, e: MouseEvent) {
    e.stopPropagation();
    this.draggingHandle = handle;
  }

  @HostListener('window:mouseup')
  stopDrag() { this.draggingHandle = null; }

  @HostListener('window:mousemove', ['$event'])
  onMouseMove(event: MouseEvent) {
    if (!this.draggingHandle || !this.spiderSvg) return;

    const rect = this.spiderSvg.nativeElement.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 200;
    const y = ((event.clientY - rect.top) / rect.height) * 200;

    const dx = x - this.centerX;
    const dy = y - this.centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    const value = Math.round(Math.min(100, Math.max(0, (dist / this.maxRadius) * 100)));

    // Wert setzen
    (this as any)[this.draggingHandle] = value;

    // Intent-Panel triggern
    this.onSliderChange(this.draggingHandle);
  }

  // ========== INTENT PANEL LOGIK ==========
  onSliderChange(dimension: Dimension): void {
    const current = (this as any)[dimension] as number;
    const baseline = this.aiBaseline[dimension];
    const delta = Math.abs(current - baseline);

    if (delta < 5) {
      this.intentSummary = null;
      this.intentIdeas = [];
      this.intentPreview = null;
      this.intentLoading = false;
      this.textApplied = false; // Reset when suggestions are cleared
      return;
    }

    this.textApplied = false; // Reset when new suggestions are being fetched
    this.requestCounter++; // Increment counter to force new request even with same values
    this.sliderChangeSubject.next({ dimension, current, baseline, requestId: this.requestCounter });
  }

  private fetchIntentSuggestions(
    dimension: Dimension,
    current: number,
    baseline: number
  ): void {
    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    // CRITICAL: Use only active chapter's content for intent suggestions
    // Use selected chapter for intent suggestions
    const targetChapterId = this.selectedAnalysisChapterId === 'all' ? null : this.selectedAnalysisChapterId;
    let text: string;

    if (targetChapterId) {
      // Use only selected chapter
      const activeChapterSentences = doc.sentences.filter(s => s.chapterId === targetChapterId);
      text = activeChapterSentences.map(s => s.text).join(' ').trim();
    } else {
      // Fallback: use all content
      text = doc.sentences.map(s => s.text).join(' ').trim();
    }

    if (!text) return;

    this.intentLoading = true;
    this.intentSummary = 'Analyzing intent...';
    this.intentIdeas = [];
    this.intentPreview = null;
    this.textApplied = false; // Reset when new suggestions are generated
    this.currentIntentDimension = dimension;

    this.aiService.getSpiderIntent({
      documentId: doc.id,
      text,
      dimension,
      currentValue: current,
      baselineValue: baseline
    }).subscribe({
      next: (res) => {
        this.intentSummary = res.summary;
        this.intentIdeas = res.ideas;
        this.intentPreview = res.preview;
        this.intentLoading = false;

        // Auto-apply logic removed as per user request.
        // User must click "Apply Text" button to insert the suggestion.
      },
      error: (err) => {
        console.error('Error fetching intent suggestions:', err);
        this.intentSummary = 'Unable to generate suggestions at this time.';
        this.intentIdeas = ['Please try again in a moment.'];
        this.intentPreview = null;
        this.intentLoading = false;
      }
    });
  }

  // ========== TABLE OF CONTENTS ==========

  /**
   * Navigate to a specific chapter
   */
  navigateToChapter(chapterId: string): void {
    this.switchTab.emit('toc');
    window.dispatchEvent(new CustomEvent('navigateToChapter', { detail: { chapterId } }));
  }

  /**
   * Check if a chapter has content (is accessible)
   */
  isChapterAccessible(chapter: Chapter): boolean {
    if (!this.currentDocument) return false;
    // A chapter is accessible if it has sentences
    return this.currentDocument.sentences.some(s => s.chapterId === chapter.id);
  }

  /**
   * Get chapter number from title (e.g., "01 Title" -> "Chapter 1")
   */
  getChapterNumber(chapter: Chapter): string {
    const match = chapter.title.match(/^(\d+)/);
    if (match) {
      const num = parseInt(match[1], 10);
      return `Chapter ${num}`;
    }
    // Fallback: use index + 1
    return `Chapter ${chapter.index + 1}`;
  }

  /**
   * Get chapter title without number (e.g., "01 Title" -> "Title")
   */
  getChapterTitle(chapter: Chapter): string {
    const match = chapter.title.match(/^\d+\s+(.+)$/);
    return match ? match[1] : chapter.title;
  }

  /**
   * Get sentence count for a chapter
   */
  getChapterSentenceCount(chapterId: string): number {
    if (!this.currentDocument) return 0;
    return this.currentDocument.sentences.filter(s => s.chapterId === chapterId).length;
  }

  /**
   * Get character count for a chapter
   */
  getChapterCharacterCount(chapterId: string): number {
    if (!this.currentDocument) return 0;
    const chapterSentences = this.currentDocument.sentences.filter(s => s.chapterId === chapterId);
    return chapterSentences.reduce((total, sentence) => total + sentence.text.length, 0);
  }

  /**
   * Format character count for display (e.g., "1,234" or "2.5K")
   */
  formatCharacterCount(count: number): string {
    if (count < 1000) {
      return count.toString();
    } else if (count < 10000) {
      return (count / 1000).toFixed(1) + 'K';
    } else {
      return Math.round(count / 1000) + 'K';
    }
  }

  /**
   * Estimate page count from character count (assuming ~2500 chars per page)
   */
  estimatePageCount(characterCount: number): number {
    return Math.max(1, Math.round(characterCount / 2500));
  }

  /**
   * Track by function for chapter ngFor
   */
  trackByChapterId(index: number, chapter: Chapter): string {
    return chapter.id;
  }
}
