import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export interface CharacterFormData {
    emoji: string;
    suggestedName?: string;
    description?: string;
    suggestedAliases?: string[];  // Word phrases to use as aliases
}

/**
 * Shared service to coordinate character creation between
 * emoji dictionary and character manager
 */
@Injectable({
    providedIn: 'root'
})
export class CharacterFormService {
    // Observable to trigger character form opening with pre-filled data
    private openFormSubject = new BehaviorSubject<CharacterFormData | null>(null);
    public openForm$ = this.openFormSubject.asObservable();

    /**
     * Request to open the character form with pre-filled data
     * (e.g., when promoting an emoji from the dictionary)
     */
    openCharacterForm(data: CharacterFormData): void {
        this.openFormSubject.next(data);
    }

    /**
     * Clear the form request (after it's been handled)
     */
    clearFormRequest(): void {
        this.openFormSubject.next(null);
    }
}
