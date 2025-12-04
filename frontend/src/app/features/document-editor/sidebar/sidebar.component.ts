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
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { AiService } from '../../../core/services/ai.service';
import { Sentence } from '../../../core/models/document.model';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit, OnDestroy {
  @Input() activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'spider-chart' = 'emojis';

  selectedSentence: Sentence | null = null;
  isGenerating = false;
  lastSuggestion: string | null = null;

  private destroy$ = new Subject<void>();

  // Emoji management
  maxEmojis = 5;
  commonEmojis = [
    '😀', '😊', '😢', '😱', '😡', '😍', '🤔', '😴',
    '🎉', '🎨', '🎭', '🎪', '🎬', '📖', '✨', '🌟',
    '🌙', '☀️', '⛈️', '🌈', '🔥', '💧', '💔', '💖',
    '👑', '👻', '🦄', '🐉', '🧙‍♂️', '🧛‍♀️', '🧜‍♂️', '🏰'
  ];

  // === Spider Chart State ===
  drama = 65;
  humor = 40;
  conflict = 80;
  mystery = 30;

  private readonly centerX = 100;
  private readonly centerY = 100;
  private readonly maxRadius = 80; // outer circle in SVG

  @ViewChild('spiderSvg') spiderSvg?: ElementRef<SVGSVGElement>;
  draggingHandle: 'drama' | 'humor' | 'conflict' | 'mystery' | null = null;

  constructor(
    private documentService: DocumentService,
    private aiService: AiService
  ) {}

  // ================= LIFECYCLE =================

  ngOnInit(): void {
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => {
        this.selectedSentence = sentence;
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
      if (el instanceof HTMLElement) {
        el.blur();
      }
    });

    setTimeout(() => {
      const doc = this.documentService.getCurrentDocument();
      if (!doc || !doc.sentences || doc.sentences.length === 0) return;

      this.isGenerating = true;
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
            this.isGenerating = false;
          }
        },
        error: (err) => {
          console.error(`Error generating emojis for sentence ${index + 1}:`, err);
          processedCount++;

          if (processedCount === totalSentences) {
            this.isGenerating = false;
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

  // ================ SPIDER CHART LOGIK =================

  private valueToPointXY(value: number, angleDeg: number): { x: number; y: number } {
    const r = (value / 100) * this.maxRadius;
    const angleRad = (angleDeg * Math.PI) / 180;
    const x = this.centerX + r * Math.cos(angleRad);
    const y = this.centerY + r * Math.sin(angleRad);
    return { x, y };
  }

  get dramaPoint()   { return this.valueToPointXY(this.drama,   -90); }
  get humorPoint()   { return this.valueToPointXY(this.humor,     0); }
  get conflictPoint(){ return this.valueToPointXY(this.conflict,  90); }
  get mysteryPoint() { return this.valueToPointXY(this.mystery,  180); }

  get spiderPoints(): string {
    const pts = [this.dramaPoint, this.humorPoint, this.conflictPoint, this.mysteryPoint];
    return pts.map(p => `${p.x},${p.y}`).join(', ');
  }

  startDrag(handle: 'drama' | 'humor' | 'conflict' | 'mystery', event: MouseEvent): void {
    event.stopPropagation();
    this.draggingHandle = handle;
  }

  @HostListener('window:mouseup')
  stopDrag(): void {
    this.draggingHandle = null;
  }

  @HostListener('window:mousemove', ['$event'])
  onMouseMove(event: MouseEvent): void {
    if (!this.draggingHandle || !this.spiderSvg) return;

    const svg = this.spiderSvg.nativeElement;
    const rect = svg.getBoundingClientRect();

    // Mausposition -> SVG-Koordinaten (0–200)
    const x = ((event.clientX - rect.left) / rect.width) * 200;
    const y = ((event.clientY - rect.top) / rect.height) * 200;

    const dx = x - this.centerX;
    const dy = y - this.centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    let value = (dist / this.maxRadius) * 100;
    value = Math.max(0, Math.min(100, value));
    const rounded = Math.round(value);

    switch (this.draggingHandle) {
      case 'drama':
        this.drama = rounded;
        break;
      case 'humor':
        this.humor = rounded;
        break;
      case 'conflict':
        this.conflict = rounded;
        break;
      case 'mystery':
        this.mystery = rounded;
        break;
    }
  }
}
