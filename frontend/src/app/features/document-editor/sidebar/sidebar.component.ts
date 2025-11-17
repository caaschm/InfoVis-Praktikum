import { Component, OnInit, OnDestroy } from '@angular/core';
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
  selectedSentence: Sentence | null = null;
  isGenerating = false;
  lastSuggestion: string | null = null;
  private destroy$ = new Subject<void>();

  // TODO: Future tabs can be added here
  activeTab = 'suggestions';

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
