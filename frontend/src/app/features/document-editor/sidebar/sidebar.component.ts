import { Component, OnInit, OnDestroy, Input } from '@angular/core';
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
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent implements OnInit, OnDestroy {
  @Input() activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' = 'emojis';

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

  constructor(
    private documentService: DocumentService,
    private aiService: AiService
  ) { }

  ngOnInit(): void {
    // Subscribe to selected sentence
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

  // Emoji management methods
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

    this.isGenerating = true;

    this.aiService.generateEmojisFromText({
      documentId: doc.id,
      sentenceId: this.selectedSentence.id,
      text: this.selectedSentence.text
    }).subscribe({
      next: (response) => {
        // Update sentence with suggested emojis
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
    const doc = this.documentService.getCurrentDocument();
    if (!doc || !doc.sentences || doc.sentences.length === 0) return;

    this.isGenerating = true;
    let processedCount = 0;
    const totalSentences = doc.sentences.length;

    // Process each sentence one by one
    doc.sentences.forEach((sentence, index) => {
      this.aiService.generateEmojisFromText({
        documentId: doc.id,
        sentenceId: sentence.id,
        text: sentence.text
      }).subscribe({
        next: (response) => {
          // Update sentence with suggested emojis
          this.documentService.updateSentenceEmojis(sentence.id, response.emojis);
          processedCount++;

          // Done when all processed
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
}
