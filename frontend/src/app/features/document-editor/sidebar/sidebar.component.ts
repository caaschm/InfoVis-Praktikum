import {
  Component,
  OnInit,
  OnDestroy,
  Input,
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
import { Sentence } from '../../../core/models/document.model';

type Dimension = 'drama' | 'humor' | 'conflict' | 'mystery';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit, OnDestroy {
  private _activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' = 'emojis';

  // ===== INTENT PANEL STATE =====
  intentSummary: string | null = null;
  intentIdeas: string[] = [];
  intentPreview: string | null = null;
  intentLoading = false;
  textApplied = false;
  private sliderChangeSubject = new Subject<{ dimension: Dimension; current: number; baseline: number }>();

  // ===== BASELINE VALUES NACH AI-ANALYSE =====
  aiBaseline: Record<Dimension, number> = {
    drama: 65,
    humor: 40,
    conflict: 80,
    mystery: 30,
  };

  @Input()
  set activeTab(value: 'emojis' | 'graph' | 'characters' | 'analysis') {
    this._activeTab = value;
    if (value === 'analysis' && !this.isAnalyzing) {
      const doc = this.documentService.getCurrentDocument();
      if (doc && doc.id !== this.lastAnalyzedDocumentId) {
        setTimeout(() => this.analyzeDocument(), 100);
      }
    }
  }

  get activeTab() {
    return this._activeTab;
  }

  selectedSentence: Sentence | null = null;

  // ===== Emoji / Text-Generation =====
  isGenerating = false;
  isGeneratingEmojisForAll = false;
  lastSuggestion: string | null = null;

  private destroy$ = new Subject<void>();

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

  constructor(
    private documentService: DocumentService,
    private aiService: AiService
  ) {}

  // ========== INIT ==========
  ngOnInit(): void {
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => this.selectedSentence = sentence);

    this.documentService.currentDocument$
      .pipe(
        takeUntil(this.destroy$),
        debounceTime(2000),
        distinctUntilChanged((prev, curr) => {
          if (!prev || !curr) return prev === curr;
          return prev.sentences.map(s => s.text).join(' ') ===
            curr.sentences.map(s => s.text).join(' ');
        })
      )
      .subscribe(doc => {
        if (doc && this.activeTab === 'analysis' && !this.isAnalyzing) {
          const currentText = doc.sentences.map(s => s.text).join(' ').trim();
          if (currentText) {
            const textHash = `${currentText.length}_${currentText.substring(0, 50)}`;
            if (textHash !== this.lastAnalyzedTextHash) {
              this.lastAnalyzedTextHash = textHash;
              this.analyzeDocument();
            }
          }
        }
      });

    // Slider-Änderungen debouncen
    this.sliderChangeSubject
      .pipe(
        takeUntil(this.destroy$),
        debounceTime(500)
      )
      .subscribe(({ dimension, current, baseline }) => {
        this.fetchIntentSuggestions(dimension, current, baseline);
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  // ================= EMOJI LOGIK =================

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
    return this.selectedSentence
      ? this.selectedSentence.emojis.length < this.maxEmojis
      : false;
  }

  generateEmojis(): void {
    if (!this.selectedSentence) return;

    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    this.isGenerating = true;

    this.aiService.generateEmojisFromText({
      documentId: doc.id,
      sentenceId: this.selectedSentence.id,
      text: this.selectedSentence.text
    }).subscribe({
      next: (response) => {
        this.documentService.updateSentenceEmojis(
          this.selectedSentence!.id,
          response.emojis
        );
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

      this.isGeneratingEmojisForAll = true;
      let processedCount = 0;
      const totalSentences = doc.sentences.length;

      this.processEmojisForAllSentences(doc, processedCount, totalSentences);
    }, 150);
  }

  private processEmojisForAllSentences(doc: any, processedCount: number, totalSentences: number): void {
    doc.sentences.forEach((sentence: Sentence, index: number) => {
      this.aiService.generateEmojisFromText({
        documentId: doc.id,
        sentenceId: sentence.id,
        text: sentence.text
      }).subscribe({
        next: (response) => {
          this.documentService.updateSentenceEmojis(sentence.id, response.emojis);
          processedCount++;
          if (processedCount === totalSentences) {
            this.isGeneratingEmojisForAll = false;
          }
        },
        error: (err) => {
          console.error(`Error generating emojis for sentence ${index + 1}:`, err);
          processedCount++;
          if (processedCount === totalSentences) {
            this.isGeneratingEmojisForAll = false;
          }
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

    this.documentService.updateSentenceText(
      this.selectedSentence.id,
      this.lastSuggestion
    );
    this.lastSuggestion = null;
  }

  applyPreviewText(): void {
    if (!this.intentPreview) return;

    // Check if text was already applied
    if (this.textApplied) {
      return;
    }

    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    // Get current document content
    const currentContent = doc.sentences.map(s => s.text).join(' ').trim();
    
    // Append the preview text to the document
    const newContent = currentContent ? `${currentContent} ${this.intentPreview}` : this.intentPreview;
    
    // Update the document content
    this.documentService.updateDocumentContent(doc.id, newContent);
    
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

  get dramaPoint()   { return this.valueToPointXY(this.drama, -90); }
  get humorPoint()   { return this.valueToPointXY(this.humor, 0); }
  get conflictPoint(){ return this.valueToPointXY(this.conflict, 90); }
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
  analyzeDocument(): void {
    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    const fullText = doc.sentences.map(s => s.text).join(' ').trim();
    if (!fullText) return;

    this.isAnalyzing = true;
    this.aiService.analyzeSpiderChart({
      documentId: doc.id,
      text: fullText
    }).subscribe({
      next: (response) => {
        this.drama = response.drama;
        this.humor = response.humor;
        this.conflict = response.conflict;
        this.mystery = response.mystery;

        this.aiBaseline = { ...response } as Record<Dimension, number>;
        this.isAnalyzing = false;

        const textHash = `${fullText.length}_${fullText.substring(0, 50)}`;
        this.lastAnalyzedTextHash = textHash;
        this.lastAnalyzedDocumentId = doc.id;
      },
      error: () => {
        this.lastAnalysisError = 'Failed to analyze text';
        this.isAnalyzing = false;
      }
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
    this.sliderChangeSubject.next({ dimension, current, baseline });
  }

  private fetchIntentSuggestions(
    dimension: Dimension,
    current: number,
    baseline: number
  ): void {
    const doc = this.documentService.getCurrentDocument();
    if (!doc) return;

    const text = doc.sentences.map(s => s.text).join(' ').trim();
    if (!text) return;

    this.intentLoading = true;
    this.intentSummary = 'Analyzing intent...';
    this.intentIdeas = [];
    this.intentPreview = null;
    this.textApplied = false; // Reset when new suggestions are generated

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
}
