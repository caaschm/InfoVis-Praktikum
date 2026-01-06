import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../../core/services/document.service';
import { CharacterHighlightService } from '../../../core/services/character-highlight.service';
import { Sentence, Character } from '../../../core/models/document.model';

@Component({
  selector: 'app-text-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './text-viewer.component.html',
  styleUrl: './text-viewer.component.scss'
})
export class TextViewerComponent implements OnInit, OnDestroy {
  sentences: Sentence[] = [];
  characters: Character[] = [];
  selectedSentenceId: string | null = null;
  hoveredCharacterId: string | null = null;
  viewMode: 'text' | 'emoji' = 'text'; // Toggle between text and emoji-only view
  showAiHighlight: boolean = false; // Toggle for AI highlight mode
  private aiGeneratedSentenceIds = new Set<string>(); // Track AI-generated sentences
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;

  constructor(

    private documentService: DocumentService,
    private characterHighlightService: CharacterHighlightService
    ,
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
          this.characters = doc.characters || [];

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

    // Subscribe to hovered character for highlighting
    this.characterHighlightService.hoveredCharacterId$
      .pipe(takeUntil(this.destroy$))
      .subscribe(characterId => {
        this.hoveredCharacterId = characterId;
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

  /**
   * Find character mentions in a sentence and return segments with character info
   */
  getTextSegments(sentenceText: string): Array<{ text: string, character: Character | null }> {
    if (!this.characters || this.characters.length === 0) {
      return [{ text: sentenceText, character: null }];
    }

    const segments: Array<{ text: string, character: Character | null }> = [];
    let remainingText = sentenceText;
    let lastIndex = 0;

    // Build a list of all character matches with their positions
    const matches: Array<{ start: number, end: number, character: Character }> = [];

    for (const character of this.characters) {
      // Check name and all aliases
      const searchTerms = [character.name, ...character.aliases];

      for (const term of searchTerms) {
        const regex = new RegExp(`\\b${term}\\b`, 'gi');
        let match;

        while ((match = regex.exec(sentenceText)) !== null) {
          matches.push({
            start: match.index,
            end: match.index + match[0].length,
            character: character
          });
        }
      }
    }

    // Sort matches by position
    matches.sort((a, b) => a.start - b.start);

    // Remove overlapping matches (keep first occurrence)
    const filteredMatches: Array<{ start: number, end: number, character: Character }> = [];
    for (const match of matches) {
      const overlaps = filteredMatches.some(existing =>
        (match.start >= existing.start && match.start < existing.end) ||
        (match.end > existing.start && match.end <= existing.end)
      );
      if (!overlaps) {
        filteredMatches.push(match);
      }
    }

    // Build segments from matches
    if (filteredMatches.length === 0) {
      return [{ text: sentenceText, character: null }];
    }

    filteredMatches.forEach((match, index) => {
      // Add text before match
      if (match.start > lastIndex) {
        segments.push({
          text: sentenceText.substring(lastIndex, match.start),
          character: null
        });
      }

      // Add matched text with character
      segments.push({
        text: sentenceText.substring(match.start, match.end),
        character: match.character
      });

      lastIndex = match.end;
    });

    // Add remaining text
    if (lastIndex < sentenceText.length) {
      segments.push({
        text: sentenceText.substring(lastIndex),
        character: null
      });
    }

    return segments;
  }

  /**
   * Check if a sentence contains mentions of a specific character
   */
  sentenceHasCharacter(sentence: Sentence, characterId: string | null): boolean {
    if (!characterId || !this.characters) {
      return false;
    }

    const character = this.characters.find(c => c.id === characterId);
    if (!character) {
      return false;
    }

    const searchTerms = [character.name, ...character.aliases];
    const text = sentence.text.toLowerCase();

    return searchTerms.some(term => {
      const regex = new RegExp(`\\b${term.toLowerCase()}\\b`);
      return regex.test(text);
    });
  }

  /**
   * Get the color of the hovered character if sentence contains it
   */
  getCharacterColor(sentence: Sentence, characterId: string | null): string {
    if (!characterId || !this.characters) {
      return '';
    }

    const character = this.characters.find(c => c.id === characterId);
    return character?.color || '';
  }
}
