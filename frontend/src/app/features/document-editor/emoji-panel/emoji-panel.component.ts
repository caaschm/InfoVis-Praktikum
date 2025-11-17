import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { Sentence } from '../../../core/models/document.model';

@Component({
  selector: 'app-emoji-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './emoji-panel.component.html',
  styleUrl: './emoji-panel.component.scss'
})
export class EmojiPanelComponent implements OnInit, OnDestroy {
  selectedSentence: Sentence | null = null;
  currentEmojis: string[] = [];
  maxEmojis = 5;
  private destroy$ = new Subject<void>();

  // Common emoji suggestions for quick selection
  commonEmojis = [
    '😀', '😊', '😢', '😱', '😡', '😍', '🤔', '😴',
    '🎉', '🎨', '🎭', '🎪', '🎬', '📖', '✨', '🌟',
    '🌙', '☀️', '⛈️', '🌈', '🔥', '💧', '💔', '💖',
    '👑', '👻', '🦄', '🐉', '🧙‍♂️', '🧛‍♀️', '🧜‍♂️', '🏰'
  ];

  constructor(private documentService: DocumentService) { }

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
}
