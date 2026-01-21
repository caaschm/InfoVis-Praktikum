import { Injectable } from '@angular/core';
import { BehaviorSubject, map } from 'rxjs';
import { DocumentService } from './document.service';
import { DocumentDetail } from '../models/document.model';

export interface WorkflowStep {
    id: string;
    icon: string;
    label: string;
    count?: number;
    status: 'empty' | 'partial' | 'ready' | 'needs-update';
    statusIcon?: string;
    aiGenerated?: boolean;
    action?: string;
    actionCallback?: () => void;
    navigateTo?: string; // Tab to navigate to
}

export interface WorkflowState {
    steps: WorkflowStep[];
    completionPercentage: number;
    currentPhase: string;
    suggestions: string[];
}

@Injectable({
    providedIn: 'root'
})
export class WorkflowTrackerService {
    private workflowState$ = new BehaviorSubject<WorkflowState>({
        steps: [],
        completionPercentage: 0,
        currentPhase: 'Getting Started',
        suggestions: []
    });

    public workflow$ = this.workflowState$.asObservable();

    constructor(private documentService: DocumentService) {
        // Update workflow state whenever document changes
        this.documentService.currentDocument$.pipe(
            map(document => this.calculateWorkflowState(document))
        ).subscribe(state => {
            this.workflowState$.next(state);
        });
    }

    private calculateWorkflowState(document: DocumentDetail | null): WorkflowState {
        const steps: WorkflowStep[] = [];
        const sentences = document?.sentences || [];
        const totalSentences = sentences.length;
        const taggedSentences = sentences.filter(s => s.emojis && s.emojis.length > 0).length;

        // Step 1: Text
        steps.push({
            id: 'text',
            icon: '📝',
            label: 'Text',
            count: totalSentences,
            status: totalSentences === 0 ? 'empty' : totalSentences < 10 ? 'partial' : 'ready',
            statusIcon: totalSentences >= 10 ? '✓' : undefined,
            navigateTo: 'ai'
        });

        // Step 2: Emojis (matches tab-strip icon 😀)
        const emojiStatus = taggedSentences === 0 ? 'empty' :
            taggedSentences < totalSentences * 0.5 ? 'partial' : 'ready';
        steps.push({
            id: 'emojis',
            icon: '😀',
            label: 'Emojis',
            count: taggedSentences,
            status: emojiStatus,
            statusIcon: taggedSentences === totalSentences ? '✓' : undefined,
            aiGenerated: true,
            action: taggedSentences === 0 && totalSentences > 0 ? 'Generate All' : undefined,
            navigateTo: 'emojis'
        });

        // Step 3: Characters (matches tab-strip icon 🎭)
        const characterCount = 0; // TODO: Get from character service
        steps.push({
            id: 'characters',
            icon: '🎭',
            label: 'Characters',
            count: characterCount,
            status: characterCount === 0 ? 'empty' : 'ready',
            statusIcon: characterCount > 0 ? '✓' : undefined,
            aiGenerated: true,
            navigateTo: 'characters'
        });

        // Step 4: Sentiment Analysis - Spider Chart with drama, mystery, humor, conflict (matches tab-strip icon 🕸️)
        steps.push({
            id: 'sentiment',
            icon: '🕸️',
            label: 'Sentiment',
            status: characterCount === 0 ? 'empty' : 'needs-update',
            statusIcon: '⚠️',
            aiGenerated: true,
            action: characterCount > 0 ? 'Analyze' : undefined,
            navigateTo: 'analysis'
        });

        // Step 5: Story Arc (matches tab-strip icon �)
        const storyArcReady = taggedSentences >= 10;
        steps.push({
            id: 'story-arc',
            icon: '📈',
            label: 'Story Arc',
            status: storyArcReady ? 'ready' : taggedSentences > 0 ? 'partial' : 'empty',
            statusIcon: storyArcReady ? '✓' : undefined,
            navigateTo: 'graph'
        });

        // Note: Removed Tension step - now using 5-step workflow

        // Calculate completion percentage
        const completedSteps = steps.filter(s => s.status === 'ready').length;
        const completionPercentage = Math.round((completedSteps / steps.length) * 100);

        // Determine current phase
        let currentPhase = 'Getting Started';
        if (totalSentences === 0) {
            currentPhase = 'Start Writing';
        } else if (taggedSentences < totalSentences * 0.5) {
            currentPhase = 'Adding Emojis';
        } else if (characterCount === 0) {
            currentPhase = 'Building Characters';
        } else if (storyArcReady) {
            currentPhase = 'Analyzing Story';
        }

        // Generate suggestions
        const suggestions = this.generateSuggestions(steps, totalSentences, taggedSentences, characterCount);

        return {
            steps,
            completionPercentage,
            currentPhase,
            suggestions
        };
    }

    private generateSuggestions(steps: WorkflowStep[], totalSentences: number, taggedSentences: number, characterCount: number): string[] {
        const suggestions: string[] = [];

        if (totalSentences === 0) {
            suggestions.push('Start by writing or pasting your story text');
        } else if (totalSentences < 10) {
            suggestions.push('Add more sentences to unlock analysis features');
        }

        if (totalSentences > 0 && taggedSentences === 0) {
            suggestions.push('Generate emojis to visualize your story flow');
        } else if (taggedSentences > 0 && taggedSentences < totalSentences * 0.3) {
            suggestions.push(`Tag ${totalSentences - taggedSentences} more sentences to see full story arc`);
        }

        if (taggedSentences >= 10 && characterCount === 0) {
            suggestions.push('Create characters to track sentiment and emotional arcs');
        }

        if (taggedSentences >= 20) {
            suggestions.push('Run story analysis to see narrative structure');
        }

        return suggestions.slice(0, 2); // Show max 2 suggestions
    }

    public navigateToStep(stepId: string): void {
        // This will be handled by the component that subscribes to this service
        // Emit navigation event or use router
        console.log('Navigate to step:', stepId);
    }

    public executeStepAction(stepId: string): void {
        // Trigger AI generation or analysis based on step
        console.log('Execute action for step:', stepId);
    }
}
