import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export type TabType = 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'workspace' | 'sentiment' | 'story-arc' | 'storyarc';

export interface WorkflowAction {
    stepId: string;
    chapterId?: string;
    action: string;
}

@Injectable({
    providedIn: 'root'
})
export class NavigationService {
    private navigateToTabSubject = new Subject<TabType>();
    public navigateToTab$ = this.navigateToTabSubject.asObservable();

    private workflowActionSubject = new Subject<WorkflowAction>();
    public workflowAction$ = this.workflowActionSubject.asObservable();

    navigateToTab(tab: TabType): void {
        // Map workflow step IDs to actual tab names
        const tabMapping: Record<string, TabType> = {
            'text': 'ai',
            'emojis': 'emojis',
            'characters': 'characters',
            'sentiment': 'analysis',
            'story-arc': 'storyarc'
        };

        const mappedTab = tabMapping[tab] || tab;
        this.navigateToTabSubject.next(mappedTab as TabType);
    }

    triggerWorkflowAction(action: WorkflowAction): void {
        this.workflowActionSubject.next(action);
    }
}
