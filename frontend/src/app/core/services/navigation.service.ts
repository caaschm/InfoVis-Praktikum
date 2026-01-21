import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export type TabType = 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'workspace' | 'sentiment' | 'story-arc';

@Injectable({
  providedIn: 'root'
})
export class NavigationService {
  private navigateToTabSubject = new Subject<TabType>();
  public navigateToTab$ = this.navigateToTabSubject.asObservable();

  navigateToTab(tab: TabType): void {
    // Map workflow step IDs to actual tab names
    const tabMapping: Record<string, TabType> = {
      'text': 'ai',
      'emojis': 'emojis',
      'characters': 'characters',
      'sentiment': 'analysis',
      'story-arc': 'graph'
    };

    const mappedTab = tabMapping[tab] || tab;
    this.navigateToTabSubject.next(mappedTab as TabType);
  }
}
