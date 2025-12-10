import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { AiService } from '../../../core/services/ai.service';
import { Sentence } from '../../../core/models/document.model';
import { WordMappingManagerComponent } from '../word-mapping-manager/word-mapping-manager.component';
import { CharacterManagerComponent } from '../character-manager/character-manager.component';
import { EmojiSetManagerComponent } from '../emoji-set-manager/emoji-set-manager.component';

@Component({
  selector: 'app-emoji-panel',
  standalone: true,
  imports: [
    CommonModule,
    WordMappingManagerComponent,
    CharacterManagerComponent,
    EmojiSetManagerComponent
  ],
  templateUrl: './emoji-panel.component.html',
  styleUrl: './emoji-panel.component.scss'
})
export class EmojiPanelComponent implements OnInit, OnDestroy {
  selectedSentence: Sentence | null = null;
  currentEmojis: string[] = [];
  maxEmojis = 5;
  isGenerating = false;
  lastSuggestion: string | null = null;
  
  // Sub-tab management within emoji panel
  activeSubTab: 'sentence' | 'words' | 'characters' | 'sets' = 'sentence';
  
  private destroy$ = new Subject<void>();

  // Common emoji suggestions for quick selection
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
        this.currentEmojis = sentence?.emojis || [];
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  addEmoji(emoji: string): void {
    if (!this.selectedSentence) return;
    if (this.currentEmojis.length >= this.maxEmojis) return;

    const newEmojis = [...this.currentEmojis, emoji];
    this.documentService.updateSentenceEmojis(this.selectedSentence.id, newEmojis);
  }

  removeEmoji(index: number): void {
    if (!this.selectedSentence) return;

    const newEmojis = this.currentEmojis.filter((_, i) => i !== index);
    this.documentService.updateSentenceEmojis(this.selectedSentence.id, newEmojis);
  }

  canAddMore(): boolean {
    return this.currentEmojis.length < this.maxEmojis;
  }

  // AI Features
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
    // Force save any pending changes
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

      doc.sentences.forEach((sentence: Sentence) => {
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
            console.error(`Error generating emojis for sentence:`, err);
            processedCount++;
            if (processedCount === totalSentences) {
              this.isGenerating = false;
            }
          }
        });
      });
    }, 150);
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
