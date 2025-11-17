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
  }

  onSentenceClick(sentence: Sentence): void {
    this.documentService.selectSentence(sentence);
  }

  onSentenceEdit(sentence: Sentence, newText: string): void {
    if (newText !== sentence.text) {
      this.documentService.updateSentenceText(sentence.id, newText);
    }
  }

  isSelected(sentenceId: string): boolean {
    return this.selectedSentenceId === sentenceId;
  }
}
