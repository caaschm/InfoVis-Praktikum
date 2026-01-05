import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { AiTrackingService } from '../../../core/services/ai-tracking.service';
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
  viewMode: 'text' | 'emoji' = 'text'; // Toggle between text and emoji-only view
  showAiHighlight: boolean = false; // Toggle for AI highlight mode
  private aiGeneratedSentenceIds = new Set<string>(); // Track AI-generated sentences
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;

  constructor(
    private documentService: DocumentService,
    private aiTrackingService: AiTrackingService
  ) { }

  ngOnInit(): void {
    // Subscribe to current document
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        if (doc) {
          const previousSentences = this.sentences;
          this.sentences = doc.sentences;
          
          // If sentences changed (re-parsed), sync AI status by text matching
          if (previousSentences.length > 0 && 
              (previousSentences.length !== doc.sentences.length || 
               previousSentences.some((s, i) => s.id !== doc.sentences[i]?.id))) {
            // Document was re-parsed, sync AI status by matching text
            this.aiTrackingService.syncSentenceIds(
              doc.sentences.map(s => ({ id: s.id, text: s.text }))
            );
          }
          
          // Sync AI-generated sentence IDs
          this.aiGeneratedSentenceIds = this.aiTrackingService.getAllAiGeneratedIds();
        }
      });

    // Subscribe to selected sentence
    this.documentService.selectedSentence$
      .pipe(takeUntil(this.destroy$))
      .subscribe(sentence => {
        this.selectedSentenceId = sentence?.id || null;
      });

    // Subscribe to AI tracking updates
    this.aiTrackingService.aiGenerated$
      .pipe(takeUntil(this.destroy$))
      .subscribe(ids => {
        this.aiGeneratedSentenceIds = ids;
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

    // IMPORTANT: Don't trigger any backend updates while user is actively typing
    // This prevents document refresh that interrupts typing and causes cursor to jump
    // 
    // Strategy:
    // 1. Update happens locally via contenteditable (user sees changes immediately)
    // 2. Debounced save only after user stops typing for 1.5 seconds
    // 3. Full document re-parse (for sentence splitting) only happens on blur
    
    this.sentenceUpdateTimer = setTimeout(() => {
      const trimmedText = newText.trim();
      if (trimmedText !== sentence.text.trim()) {
        // Only update sentence text (not full document re-parse) while user is typing
        // Full document re-parse with sentence splitting happens on blur
        this.documentService.updateSentenceText(sentence.id, trimmedText);
      }
    }, 1500); // Longer delay to avoid interrupting typing
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
      const hasMultipleSentences = trimmedNewText.split(/[.!?]\s+(?=\S)/).length > 1;

      if (hasMultipleSentences) {
        // Only re-parse document when user finishes editing (on blur)
        // This prevents interruption while typing
        const currentDoc = this.documentService.getCurrentDocument();
        if (currentDoc) {
          const updatedSentences = this.sentences.map(s =>
            s.id === sentence.id ? trimmedNewText : s.text
          );
          const fullText = updatedSentences.join(' ').trim();
          
          // Update document content to trigger sentence splitting
          // This happens only after user stops editing, so it won't interrupt typing
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

  toggleViewMode(): void {
    this.viewMode = this.viewMode === 'text' ? 'emoji' : 'text';
  }

  toggleAiHighlight(): void {
    this.showAiHighlight = !this.showAiHighlight;
  }

  isAiGenerated(sentenceId: string): boolean {
    return this.aiGeneratedSentenceIds.has(sentenceId);
  }

  markAsAiGenerated(sentenceId: string): void {
    this.aiTrackingService.markAsAiGenerated(sentenceId);
  }

  unmarkAsAiGenerated(sentenceId: string): void {
    this.aiTrackingService.unmarkAsAiGenerated(sentenceId);
  }
}
