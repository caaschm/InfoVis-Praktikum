import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Tracks the current Workspace scope (All Chapters vs specific chapter).
 * Used by Character Sentiment "Link" toggle to follow Workspace scope.
 */
@Injectable({
  providedIn: 'root'
})
export class WorkspaceScopeService {
  /** null = All Chapters, string = chapter id */
  private scopeChapterIdSubject = new BehaviorSubject<string | null>(null);
  public scopeChapterId$: Observable<string | null> = this.scopeChapterIdSubject.asObservable();

  setScope(chapterId: string | null): void {
    this.scopeChapterIdSubject.next(chapterId);
  }

  getScope(): string | null {
    return this.scopeChapterIdSubject.value;
  }
}
