import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Service to manage character highlighting across components
 * When a character is hovered in the character manager,
 * all mentions in the text viewer should highlight
 */
@Injectable({
  providedIn: 'root'
})
export class CharacterHighlightService {
  private hoveredCharacterIdSubject = new BehaviorSubject<string | null>(null);
  public hoveredCharacterId$: Observable<string | null> = this.hoveredCharacterIdSubject.asObservable();

  setHoveredCharacter(characterId: string | null): void {
    this.hoveredCharacterIdSubject.next(characterId);
  }

  clearHoveredCharacter(): void {
    this.hoveredCharacterIdSubject.next(null);
  }
}
