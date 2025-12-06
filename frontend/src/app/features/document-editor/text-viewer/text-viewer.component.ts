import { Component, OnInit, OnDestroy, ElementRef, ViewChild } from '@angular/core';
// The original errors are linter/TypeScript "Cannot find module ... or its corresponding type declarations"
// This is not a code issue within this file, but rather a project configuration/dependency issue.
// However, to address possible code-level issues: ensure all imports are valid and used.
// Imports are correct if those modules exist and are installed. However, if you're getting errors like
// "Cannot find module ... or its corresponding type declarations", it means you need to install the
// corresponding npm packages and possibly their type declarations.

// For Angular modules and RxJS, make sure you have installed these in your project:
//   npm install @angular/common @angular/forms rxjs
// TypeScript projects may also benefit from (rarely needed for Angular, but useful elsewhere):
//   npm install --save-dev @types/angular @types/node

import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { ChapterService } from '../../../core/services/chapter.service'
import { Sentence, Chapter } from '../../../core/models/document.model';

@Component({
  selector: 'app-text-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './text-viewer.component.html',
  styleUrls: ['./text-viewer.component.scss']
})
export class TextViewerComponent implements OnInit, OnDestroy {
  @ViewChild('chapterContainer', { static: false }) chapterContainer!: ElementRef;
  @ViewChild('chapterInput', { static: false }) chapterInput!: ElementRef<HTMLInputElement>;

  sentences: Sentence[] = [];
  chapters: Chapter[] = [];
  selectedSentenceId: string | null = null;
  selectedChapterId: string | null = null;
  viewMode: 'text' | 'emoji' = 'text';
  showAddChapterDialog = false;
  newChapterTitle = '';
  showTableOfContents = false;
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;

  constructor(
    private documentService: DocumentService,
    private chapterService: ChapterService
  ) { }

  ngOnInit(): void {
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        if (doc) {
          this.sentences = doc.sentences;
          this.chapters = doc.chapters || [];
          this.loadChapters(doc.id);
          
          // Auto-assign ALL unassigned sentences to the first chapter if it exists
          if (this.chapters.length > 0 && this.sentences.length > 0) {
            const unassignedSentences = this.sentences.filter(s => !s.chapterId);
            if (unassignedSentences.length > 0) {
              const firstChapter = this.chapters.sort((a, b) => a.index - b.index)[0];
              // Assign all unassigned sentences to the first chapter
              unassignedSentences.forEach(sentence => {
                this.documentService.updateSentenceChapter(sentence.id, firstChapter.id);
              });
              
              // Refresh after assignment
              setTimeout(() => {
                this.documentService.getDocument(doc.id).subscribe(updatedDoc => {
                  if (updatedDoc) {
                    this.sentences = updatedDoc.sentences;
                    this.chapters = updatedDoc.chapters || [];
                  }
                });
              }, 300);
            }
          }
        }
      });

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

  loadChapters(documentId: string): void {
    this.chapterService.getChapters(documentId).subscribe(chapters => {
      this.chapters = chapters.sort((a, b) => a.index - b.index);
    });
  }

  onChapterSelect(chapterId: string | null): void {
    this.selectedChapterId = chapterId;
    if (chapterId) {
      // Scroll to the selected chapter
      setTimeout(() => {
        const chapterElement = document.getElementById(`chapter-${chapterId}`);
        if (chapterElement) {
          chapterElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    } else {
      // When "All Chapters" is selected, scroll to top
      const chapterContainer = this.chapterContainer?.nativeElement;
      if (chapterContainer) {
        chapterContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }

  openAddChapterDialog(): void {
    this.showAddChapterDialog = true;
    // Auto-generate next chapter number
    const nextChapterNumber = this.getNextChapterNumber();
    this.newChapterTitle = nextChapterNumber;
    
    // Auto-focus input after dialog opens
    setTimeout(() => {
      if (this.chapterInput) {
        this.chapterInput.nativeElement.focus();
        this.chapterInput.nativeElement.select();
      }
    }, 100);
  }

  getNextChapterNumber(): string {
    // Find the highest chapter number and increment
    if (this.chapters.length === 0) {
      return '01';
    }
    
    // Extract numbers from existing chapter titles
    const chapterNumbers = this.chapters
      .map(ch => {
        const match = ch.title.match(/^(\d+)/);
        return match ? parseInt(match[1], 10) : 0;
      })
      .filter(num => num > 0);
    
    if (chapterNumbers.length === 0) {
      return '01';
    }
    
    const maxNumber = Math.max(...chapterNumbers);
    const nextNumber = maxNumber + 1;
    return nextNumber.toString().padStart(2, '0');
  }

  closeAddChapterDialog(): void {
    this.showAddChapterDialog = false;
    this.newChapterTitle = '';
  }

  addChapter(): void {
    const currentDoc = this.documentService.getCurrentDocument();
    if (currentDoc) {
      const title = this.newChapterTitle.trim() || this.getNextChapterNumber();
      
      this.chapterService.createChapter(currentDoc.id, title).subscribe({
        next: (chapter) => {
          this.chapters.push(chapter);
          this.chapters.sort((a, b) => a.index - b.index);
          
          // If this is the FIRST chapter, assign all existing unassigned sentences to it
          if (this.chapters.length === 1) {
            const unassignedSentences = this.getAllSentencesWithoutChapter();
            if (unassignedSentences.length > 0) {
              unassignedSentences.forEach(sentence => {
                this.documentService.updateSentenceChapter(sentence.id, chapter.id);
              });
            }
          }
          
          this.closeAddChapterDialog();
          // Show all chapters so user can see the new chapter
          this.selectedChapterId = null;
          
          // Refresh document after a short delay to allow backend to process
          setTimeout(() => {
            this.documentService.getDocument(currentDoc.id).subscribe(doc => {
              if (doc) {
                this.sentences = doc.sentences;
                this.chapters = doc.chapters || [];
                this.chapters.sort((a, b) => a.index - b.index);
              }
            });
          }, 300);
        },
        error: (err) => {
          console.error('Full error object:', err);
          const errorMessage = err.error?.detail || err.message || 'Failed to create chapter. Please try again.';
          alert(`Error: ${errorMessage}\n\nCheck the browser console for details.`);
        }
      });
    } else {
      alert('No document loaded. Please create or load a document first.');
    }
  }

  getSentencesForChapter(chapterId: string | undefined): Sentence[] {
    if (!chapterId) {
      return this.sentences.filter(s => !s.chapterId);
    }
    return this.sentences.filter(s => s.chapterId === chapterId);
  }

  getAllSentencesWithoutChapter(): Sentence[] {
    return this.sentences.filter(s => !s.chapterId);
  }

  toggleTableOfContents(): void {
    this.showTableOfContents = !this.showTableOfContents;
  }

  updateChapterTitle(chapter: Chapter, newTitle: string): void {
    const trimmedTitle = newTitle.trim();
    if (trimmedTitle && trimmedTitle !== chapter.title) {
      this.chapterService.updateChapter(chapter.id, trimmedTitle).subscribe({
        next: (updatedChapter) => {
          const index = this.chapters.findIndex(c => c.id === chapter.id);
          if (index !== -1) {
            this.chapters[index] = updatedChapter;
          }
        },
        error: (err) => {
          console.error('Error updating chapter title:', err);
        }
      });
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

    // 🔄 AUTO-SAVE: Check if user typed sentence-ending punctuation followed by space AND more content
    // Only triggers when user is actually starting a new sentence, not just ending current one
    const hasNewSentence = /[.!?]\s+\S/.test(newText);

    if (hasNewSentence) {
      // 🔄 IMMEDIATE save when new sentence detected - triggers sentence splitting
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
    } else {
      // For non-punctuation changes, debounce the update
      this.sentenceUpdateTimer = setTimeout(() => {
        this.documentService.updateSentenceText(sentence.id, newText.trim());
      }, 500);
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
      const hasMultipleSentences = trimmedNewText.split(/[.!?]\s+(?=\S)/).length > 1;

      if (hasMultipleSentences) {
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

  toggleViewMode(): void {
    this.viewMode = this.viewMode === 'text' ? 'emoji' : 'text';
  }

  formatChapterNumber(index: number): string {
    return index.toString().padStart(2, '0');
  }

  getChapterDisplayTitle(chapter: Chapter, index: number): string {
    // If title already starts with a number, use it as-is
    // Otherwise, prepend the formatted number
    if (/^\d+/.test(chapter.title)) {
      return chapter.title;
    }
    return `${this.formatChapterNumber(index + 1)} ${chapter.title}`;
  }

  getVisibleSentences(): Sentence[] {
    // If a specific chapter is selected, only show sentences from that chapter
    if (this.selectedChapterId) {
      return this.getSentencesForChapter(this.selectedChapterId);
    }
    // Otherwise, show all sentences (from all chapters and unassigned)
    return this.sentences;
  }

  getVisibleChapters(): Chapter[] {
    // If a specific chapter is selected, only show that chapter
    if (this.selectedChapterId) {
      const chapter = this.chapters.find(c => c.id === this.selectedChapterId);
      return chapter ? [chapter] : [];
    }
    // Otherwise, show all chapters sorted by index
    return [...this.chapters].sort((a, b) => a.index - b.index);
  }

  onChapterTitleKeyDown(event: KeyboardEvent, chapter: Chapter): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      const target = event.target as HTMLElement;
      const newTitle = target.innerText.trim();
      
      // Save the title
      this.updateChapterTitle(chapter, newTitle);
      
      // Remove focus from the title
      target.blur();
      
      // Focus on the editable area for this chapter
      setTimeout(() => {
        const chapterContent = target.parentElement?.querySelector('.chapter-content') as HTMLElement;
        if (chapterContent) {
          // First, try to focus on existing sentence
          const firstSentence = chapterContent.querySelector('.sentence-text') as HTMLElement;
          if (firstSentence) {
            firstSentence.focus();
            // Move cursor to end
            const range = document.createRange();
            range.selectNodeContents(firstSentence);
            range.collapse(false);
            const selection = window.getSelection();
            selection?.removeAllRanges();
            selection?.addRange(range);
          } else {
            // No sentences exist, focus on the empty chapter hint
            const emptyHint = chapterContent.querySelector('.empty-chapter-hint') as HTMLElement;
            if (emptyHint) {
              emptyHint.focus();
              // Clear placeholder text
              if (emptyHint.innerText.trim() === 'Start typing here...') {
                emptyHint.innerText = '';
              }
            } else {
              // Create a temporary editable area if placeholder doesn't exist
              this.focusChapterContent(chapterContent, chapter);
            }
          }
        }
      }, 100);
    }
  }

  private focusChapterContent(chapterContent: HTMLElement, chapter: Chapter): void {
    // Create a temporary editable div if needed
    const tempEditor = document.createElement('div');
    tempEditor.className = 'empty-chapter-hint';
    tempEditor.contentEditable = 'true';
    tempEditor.setAttribute('data-placeholder', 'Start typing here...');
    tempEditor.textContent = '';
    tempEditor.addEventListener('focus', (e) => this.onEmptyChapterFocus(e as FocusEvent, chapter));
    tempEditor.addEventListener('blur', (e) => this.onEmptyChapterBlur(e as FocusEvent, chapter));
    tempEditor.addEventListener('keydown', (e) => this.onEmptyChapterKeyDown(e as KeyboardEvent, chapter));
    
    chapterContent.appendChild(tempEditor);
    tempEditor.focus();
  }

  onEmptyChapterFocus(event: FocusEvent, chapter: Chapter): void {
    const target = event.target as HTMLElement;
    // Clear placeholder text when focused
    if (target.innerText.trim() === 'Start typing here...') {
      target.innerText = '';
    }
    // Ensure the element is editable and focusable
    target.setAttribute('contenteditable', 'true');
    target.focus();
  }

  onEmptyChapterKeyDown(event: KeyboardEvent, chapter: Chapter): void {
    const target = event.target as HTMLElement;
    
    // Handle Enter key - create sentence and move to next line
    if (event.key === 'Enter') {
      event.preventDefault();
      const text = target.innerText.trim();
      
      if (text && text !== 'Start typing here...') {
        this.createSentenceFromText(text, chapter);
        target.innerText = '';
      }
    }
  }

  onEmptyChapterBlur(event: FocusEvent, chapter: Chapter): void {
    const target = event.target as HTMLElement;
    const text = target.innerText.trim();
    
    // If user typed something, create a sentence
    if (text && text !== 'Start typing here...') {
      this.createSentenceFromText(text, chapter);
    }
    
    // Restore placeholder if empty
    if (!text || text === 'Start typing here...') {
      target.innerText = 'Start typing here...';
    }
  }

  private createSentenceFromText(text: string, chapter: Chapter): void {
    const currentDoc = this.documentService.getCurrentDocument();
    if (currentDoc) {
      // Get sentences for THIS chapter only
      const chapterSentences = this.getSentencesForChapter(chapter.id);
      
      // If chapter already has sentences, append to the last one
      if (chapterSentences.length > 0) {
        const lastSentence = chapterSentences[chapterSentences.length - 1];
        const updatedText = `${lastSentence.text} ${text}`;
        this.documentService.updateSentenceText(lastSentence.id, updatedText);
        return;
      }
      
      // No sentences yet - create new sentence for THIS chapter only
      // Build content maintaining strict chapter boundaries
      const chapters = [...this.chapters].sort((a, b) => a.index - b.index);
      
      // Store original sentence counts per chapter
      const originalCounts: { [chapterId: string]: number } = {};
      chapters.forEach(ch => {
        originalCounts[ch.id] = this.getSentencesForChapter(ch.id).length;
      });
      
      // Build content parts - each chapter's content separately
      const contentParts: string[] = [];
      
      chapters.forEach(ch => {
        if (ch.id === chapter.id) {
          // This chapter gets ONLY the new text
          contentParts.push(text);
        } else {
          // Other chapters keep their existing content
          const chSentences = this.getSentencesForChapter(ch.id);
          if (chSentences.length > 0) {
            contentParts.push(chSentences.map(s => s.text).join(' '));
          }
        }
      });
      
      // Add unassigned sentences (should be none if first chapter assignment worked)
      const unassigned = this.getAllSentencesWithoutChapter();
      if (unassigned.length > 0) {
        contentParts.push(unassigned.map(s => s.text).join(' '));
      }
      
      const fullContent = contentParts.join(' ');
      
      // Calculate which sentence index the new text will be at
      let sentenceIndexOffset = 0;
      const chapterIndex = chapters.findIndex(ch => ch.id === chapter.id);
      for (let i = 0; i < chapterIndex; i++) {
        sentenceIndexOffset += originalCounts[chapters[i].id];
      }
      
      // Update document content
      this.documentService.updateDocumentContent(currentDoc.id, fullContent);
      
      // After update, assign the new sentence to this chapter based on position
      setTimeout(() => {
        this.documentService.getDocument(currentDoc.id).subscribe(doc => {
          if (doc) {
            this.sentences = doc.sentences;
            
            // Find the sentence at the expected position (should be the new one)
            const newSentence = doc.sentences[sentenceIndexOffset];
            if (newSentence && newSentence.text.trim() === text.trim() && newSentence.chapterId !== chapter.id) {
              this.documentService.updateSentenceChapter(newSentence.id, chapter.id);
            }
            
            // Also reassign any other sentences that lost their chapter assignment
            this.reassignExistingSentencesToChapters(doc.sentences, chapters, originalCounts);
            
            // Refresh
            setTimeout(() => {
              this.documentService.getDocument(currentDoc.id).subscribe(updatedDoc => {
                if (updatedDoc) {
                  this.sentences = updatedDoc.sentences;
                  this.chapters = updatedDoc.chapters || [];
                }
              });
            }, 300);
          }
        });
      }, 500);
    }
  }

  private reassignExistingSentencesToChapters(
    allSentences: Sentence[],
    chapters: Chapter[],
    originalCounts: { [chapterId: string]: number }
  ): void {
    // Store original assignments by text
    const originalAssignments = new Map<string, string | undefined>();
    this.sentences.forEach(s => {
      originalAssignments.set(s.text.trim(), s.chapterId);
    });
    
    // Reassign sentences based on their original chapter
    allSentences.forEach(sentence => {
      const originalChapterId = originalAssignments.get(sentence.text.trim());
      if (originalChapterId && sentence.chapterId !== originalChapterId) {
        this.documentService.updateSentenceChapter(sentence.id, originalChapterId);
      }
    });
  }
}
