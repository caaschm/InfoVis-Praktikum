import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { Sentence } from '../../../core/models/document.model';

@Component({
  selector: 'app-text-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './text-viewer.component.html',
  styleUrl: './text-viewer.component.scss'
})
export class TextViewerComponent implements OnInit, OnDestroy {
  sentences: Sentence[] = [];
  selectedSentenceId: string | null = null;
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;

  constructor(private documentService: DocumentService) { }

  ngOnInit(): void {
    // Subscribe to current document
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        if (doc) {
          this.sentences = doc.sentences;
        }
      });

    // Subscribe to selected sentence
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => {
        this.selectedSentenceId = sentence?.id || null;
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
    }
  }

  onSentenceClick(sentence: Sentence): void {
    this.documentService.selectSentence(sentence);
  }

  onSentenceInput(sentence: Sentence, newText: string): void {
    // Clear any existing timer
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
    }

    // Check if user typed sentence-ending punctuation followed by space
    const hasNewSentence = /[.!?]\s+\w/.test(newText);
    
    if (hasNewSentence) {
      // User is typing a new sentence after punctuation - trigger re-parse
      this.sentenceUpdateTimer = setTimeout(() => {
        const currentDoc = this.documentService.getCurrentDocument();
        if (currentDoc) {
          // Rebuild full document text with the updated sentence
          const updatedSentences = this.sentences.map(s => 
            s.id === sentence.id ? newText.trim() : s.text
          );
          const fullText = updatedSentences.join(' ').trim();
          
          // Only update if text actually changed
          const currentFullText = this.sentences.map(s => s.text).join(' ').trim();
          if (fullText !== currentFullText) {
            this.documentService.updateDocumentContent(currentDoc.id, fullText);
          }
        }
      }, 800); // Increased to 800ms for better UX
    }
  }

  onSentenceBlur(sentence: Sentence, newText: string): void {
    // Clear any pending timer
    if (this.sentenceUpdateTimer) {
      clearTimeout(this.sentenceUpdateTimer);
      this.sentenceUpdateTimer = null;
    }

    const trimmedNewText = newText.trim();
    const trimmedOldText = sentence.text.trim();

    if (trimmedNewText !== trimmedOldText) {
      // Check if text contains sentence-ending punctuation that could create new sentences
      const hasPunctuation = /[.!?]/.test(trimmedNewText);
      const hasMultipleSentences = trimmedNewText.split(/[.!?]\s+/).length > 1;
      
      if (hasPunctuation && hasMultipleSentences) {
        // Re-parse the entire document to split sentences
        const currentDoc = this.documentService.getCurrentDocument();
        if (currentDoc) {
          const updatedSentences = this.sentences.map(s => 
            s.id === sentence.id ? trimmedNewText : s.text
          );
          const fullText = updatedSentences.join(' ').trim();
          this.documentService.updateDocumentContent(currentDoc.id, fullText);
        }
      } else {
        // Just update this sentence text without re-parsing
        this.documentService.updateSentenceText(sentence.id, trimmedNewText);
      }
    }
  }

  isSelected(sentenceId: string): boolean {
    return this.selectedSentenceId === sentenceId;
  }
}
