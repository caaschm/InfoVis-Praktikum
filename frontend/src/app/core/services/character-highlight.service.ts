import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Service to manage highlighting across components
 * Supports highlighting by character ID or by sentence IDs
 */
@Injectable({
  providedIn: 'root'
})
export class CharacterHighlightService {
  private hoveredCharacterIdSubject = new BehaviorSubject<string | null>(null);
  public hoveredCharacterId$: Observable<string | null> = this.hoveredCharacterIdSubject.asObservable();

  private hoveredSentenceIdsSubject = new BehaviorSubject<string[]>([]);
  public hoveredSentenceIds$: Observable<string[]> = this.hoveredSentenceIdsSubject.asObservable();

  private highlightColorSubject = new BehaviorSubject<string>('#999999');
  public highlightColor$: Observable<string> = this.highlightColorSubject.asObservable();

  setHoveredCharacter(characterId: string | null, color: string = '#999999'): void {
    this.hoveredCharacterIdSubject.next(characterId);
    this.hoveredSentenceIdsSubject.next([]);
    this.highlightColorSubject.next(color);
  }

  setHoveredSentences(sentenceIds: string[], color: string = '#999999'): void {
    this.hoveredSentenceIdsSubject.next(sentenceIds);
    this.hoveredCharacterIdSubject.next(null);
    this.highlightColorSubject.next(color);
  }

  clearHover(): void {
    this.hoveredCharacterIdSubject.next(null);
    this.hoveredSentenceIdsSubject.next([]);
    this.highlightColorSubject.next('#999999');
  }
}
