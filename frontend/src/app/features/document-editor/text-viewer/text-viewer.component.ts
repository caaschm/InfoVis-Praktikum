import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
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
  hoveredEmoji: string | null = null;
  highlightColor: string = '#999999';
  viewMode: 'text' | 'emoji' = 'text'; // Toggle between text and emoji-only view
  showAiHighlight: boolean = false; // Toggle for AI highlight mode
  private aiGeneratedSentenceIds = new Set<string>(); // Track AI-generated sentences
  private destroy$ = new Subject<void>();
  private sentenceUpdateTimer: any = null;

  constructor(

    private documentService: DocumentService,
    private characterHighlightService: CharacterHighlightService,
    private cdr: ChangeDetectorRef
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

    // Subscribe to hovered emoji for highlighting
    this.characterHighlightService.hoveredEmoji$
      .pipe(takeUntil(this.destroy$))
      .subscribe(emoji => {
        console.log('👁️ [TEXT-VIEWER] Received hovered emoji:', emoji);
        this.hoveredEmoji = emoji;
        this.cdr.markForCheck();
      });

    // Subscribe to highlight color
    this.characterHighlightService.highlightColor$
      .pipe(takeUntil(this.destroy$))
      .subscribe(color => {
        this.highlightColor = color;
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
    getTextSegments(sentenceText: string): Array < { text: string, character: Character | null } > {
      if(!this.characters || this.characters.length === 0) {
      return [{ text: sentenceText, character: null }];
    }

    const segments: Array<{ text: string, character: Character | null }> = [];
    const segments: Array<{ text: string, character: Character | null }> = [];
    let remainingText = sentenceText;
    let lastIndex = 0;

    // Build a list of all character matches with their positions
    const matches: Array<{ start: number, end: number, character: Character }> = [];

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
    const filteredMatches: Array<{ start: number, end: number, character: Character }> = [];
    for (const match of matches) {
      const overlaps = filteredMatches.some(existing =>
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
     * Check if a sentence contains the hovered emoji
     */
    sentenceHasHoveredEmoji(sentence: Sentence): boolean {
      if (!this.hoveredEmoji) return false;
      return sentence.emojis.includes(this.hoveredEmoji);
    }

    /**
     * Get text segments with word-level highlighting for hovered emoji
     * Returns array of {text, isHighlighted}
     */
    getHighlightedSegments(sentence: Sentence): Array < { text: string, isHighlighted: boolean } > {
      if(!this.hoveredEmoji) {
      return [{ text: sentence.text, isHighlighted: false }];
    }

    // Collect all phrases to highlight for this emoji
    let phrases: string[] = [];

    // STRATEGY 1: Check if this emoji belongs to a CHARACTER
    const charactersWithEmoji = this.characters.filter(c => c.emoji === this.hoveredEmoji);

    if (charactersWithEmoji.length > 0) {
      // This emoji IS a character - use character's word phrases
      // Combines all phrases from all characters using this emoji (e.g., "Hero" and "Red Hero" both use 🦸)
      for (const character of charactersWithEmoji) {
        if (character.wordPhrases && character.wordPhrases.length > 0) {
          phrases.push(...character.wordPhrases);
        }
      }
    } else {
      // STRATEGY 2: This emoji is a RECURRING THEME (not promoted to character yet)
      // Use the sentence's emoji_mappings to find what words it represents
      if (sentence.emojis.includes(this.hoveredEmoji) && sentence.emojiMappings && this.hoveredEmoji in sentence.emojiMappings) {
        phrases = sentence.emojiMappings[this.hoveredEmoji] || [];
      }
    }

    if (phrases.length === 0) {
      // No mapping available - don't highlight anything
      return [{ text: sentence.text, isHighlighted: false }];
    }

    // Find all phrase occurrences in the text using word boundaries
    const segments: Array<{ text: string, isHighlighted: boolean }> = [];

    // Build a list of matches with positions
    const matches: Array<{ start: number, end: number, phrase: string }> = [];
    for (const phrase of phrases) {
      // Use word boundary regex to avoid false matches (e.g., "hero" shouldn't match "heroic")
      const escapedPhrase = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`\\b${escapedPhrase}\\b`, 'gi');
      let match;
      while ((match = regex.exec(sentence.text)) !== null) {
        matches.push({
          start: match.index,
          end: match.index + match[0].length,
          phrase: match[0]
        });
      }
    }

    // Sort matches by position and remove overlaps
    matches.sort((a, b) => a.start - b.start);
    const filteredMatches: Array<{ start: number, end: number }> = [];
    for (const match of matches) {
      const overlaps = filteredMatches.some(existing =>
        (match.start >= existing.start && match.start < existing.end) ||
        (match.end > existing.start && match.end <= existing.end)
      );
      if (!overlaps) {
        filteredMatches.push(match);
      }
    }

    // Build segments
    if (filteredMatches.length === 0) {
      return [{ text: sentence.text, isHighlighted: false }];
    }

    let lastIndex = 0;
    for (const match of filteredMatches) {
      // Add text before match
      if (match.start > lastIndex) {
        segments.push({
          text: sentence.text.substring(lastIndex, match.start),
          isHighlighted: false
        });
      }
      // Add highlighted match
      segments.push({
        text: sentence.text.substring(match.start, match.end),
        isHighlighted: true
      });
      lastIndex = match.end;
    }

    // Add remaining text
    if (lastIndex < sentence.text.length) {
      segments.push({
        text: sentence.text.substring(lastIndex),
        isHighlighted: false
      });
    }

    return segments;
  }
}
