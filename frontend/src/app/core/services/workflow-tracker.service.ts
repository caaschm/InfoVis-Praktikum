import { Injectable } from '@angular/core';
import { BehaviorSubject, map } from 'rxjs';
import { DocumentService } from './document.service';
import { DocumentDetail, Chapter, Sentence } from '../models/document.model';

// ========== Types ==========

export interface WorkflowStep {
    id: string;
    icon: string;
    label: string;
    count?: number;
    total?: number;
    status: 'empty' | 'partial' | 'ready';
    statusText?: string;
    aiGenerated?: boolean;
    action?: string;
    navigateTo?: string;
    tooltip?: string;
}

export interface ChapterProgress {
    chapterId: string;
    chapterTitle: string;
    sentenceCount: number;
    emojiCount: number;
    percentage: number;
}

export interface StorySection {
    chapters: number;
    sentences: number;
    isReady: boolean;
}

export interface UnderstandSection {
    emojis: WorkflowStep;
    characters: WorkflowStep;
    sentiment: WorkflowStep;
    chapterProgress: ChapterProgress[];
}

export interface CraftSection {
    storyArc: WorkflowStep;
    mood: WorkflowStep;
}

export interface WorkflowState {
    story: StorySection;
    understand: UnderstandSection;
    craft: CraftSection;
    overallProgress: number;
    nextSuggestion: string;
}

// ========== Service ==========

@Injectable({
    providedIn: 'root'
})
export class WorkflowTrackerService {
    private workflowState$ = new BehaviorSubject<WorkflowState>(this.getEmptyState());

    public workflow$ = this.workflowState$.asObservable();

    constructor(private documentService: DocumentService) {
        this.documentService.currentDocument$.pipe(
            map(document => this.calculateWorkflowState(document))
        ).subscribe(state => {
            this.workflowState$.next(state);
        });
    }

    private getEmptyState(): WorkflowState {
        return {
            story: { chapters: 0, sentences: 0, isReady: false },
            understand: {
                emojis: { id: 'emojis', icon: '😀', label: 'Emojis', status: 'empty', navigateTo: 'emojis' },
                characters: { id: 'characters', icon: '🎭', label: 'Characters', status: 'empty', navigateTo: 'characters' },
                sentiment: { id: 'sentiment', icon: '💭', label: 'Sentiment', status: 'empty', navigateTo: 'characters' },
                chapterProgress: []
            },
            craft: {
                storyArc: { id: 'story-arc', icon: '📈', label: 'Story Arc', status: 'empty', navigateTo: 'graph' },
                mood: { id: 'mood', icon: '🕸️', label: 'Mood', status: 'empty', navigateTo: 'analysis' }
            },
            overallProgress: 0,
            nextSuggestion: 'Start by writing or pasting your story'
        };
    }

    private calculateWorkflowState(document: DocumentDetail | null): WorkflowState {
        if (!document) return this.getEmptyState();

        const sentences = document.sentences || [];
        const chapters = document.chapters || [];
        const characters = document.characters || [];

        const totalSentences = sentences.length;
        const totalChapters = chapters.length || 1;
        const characterCount = characters.length;

        // Calculate per-chapter progress
        const chapterProgress = this.calculateChapterProgress(chapters, sentences);
        const chaptersWithEmojis = chapterProgress.filter(cp => cp.percentage === 100).length;
        const totalTagged = sentences.filter(s => s.emojis?.length > 0).length;

        // ===== STORY SECTION =====
        const story: StorySection = {
            chapters: totalChapters,
            sentences: totalSentences,
            isReady: totalSentences >= 5
        };

        // ===== UNDERSTAND SECTION =====

        // Emojis - per chapter
        const emojis: WorkflowStep = {
            id: 'emojis',
            icon: '😀',
            label: 'Emoji Creation',
            count: chaptersWithEmojis,
            total: totalChapters,
            status: totalTagged === 0 ? 'empty' : chaptersWithEmojis === totalChapters ? 'ready' : 'partial',
            statusText: totalTagged === 0 ? 'Not started' : `${chaptersWithEmojis}/${totalChapters} chapters tagged`,
            aiGenerated: true,
            action: totalSentences > 0 ? 'generateEmojis' : undefined,
            navigateTo: 'ai',
            tooltip: 'Visualize content with emojis per sentence'
        };

        // Characters
        const charactersStep: WorkflowStep = {
            id: 'characters',
            icon: '🎭',
            label: 'Characters',
            count: characterCount,
            status: characterCount === 0 ? 'empty' : 'ready',
            statusText: characterCount === 0 ? 'None defined' : `${characterCount} found`,
            navigateTo: 'emojis',
            tooltip: 'Track who appears in your story'
        };

        // Character Sentiment - works with or without pre-defined characters
        const sentiment: WorkflowStep = {
            id: 'sentiment',
            icon: '💭',
            label: 'Sentiment',
            status: totalSentences < 5 ? 'empty' : 'ready',
            statusText: totalSentences < 5 ? 'Need more text' : 'Available',
            aiGenerated: true,
            action: totalSentences >= 5 ? 'Analyze' : undefined,
            navigateTo: 'characters',
            tooltip: characterCount > 0
                ? 'See how characters are portrayed'
                : 'AI will discover characters automatically'
        };

        const understand: UnderstandSection = {
            emojis,
            characters: charactersStep,
            sentiment,
            chapterProgress
        };

        // ===== CRAFT SECTION =====

        // Story Arc - only needs text
        const storyArc: WorkflowStep = {
            id: 'story-arc',
            icon: '📈',
            label: 'Story Arc',
            status: totalSentences < 5 ? 'empty' : 'ready',
            statusText: totalSentences < 5 ? 'Need more text' : 'Available',
            aiGenerated: true,
            action: totalSentences >= 5 ? 'View' : undefined,
            navigateTo: 'storyarc',
            tooltip: 'Analyze narrative tension across your story'
        };

        // Mood / Spider Chart - only needs text
        const mood: WorkflowStep = {
            id: 'mood',
            icon: '🕸️',
            label: 'Mood',
            status: totalSentences < 3 ? 'empty' : 'ready',
            statusText: totalSentences < 3 ? 'Need more text' : 'Available',
            aiGenerated: true,
            action: totalSentences >= 3 ? 'Analyze' : undefined,
            navigateTo: 'analysis',
            tooltip: 'Balance drama, humor, conflict, mystery'
        };

        const craft: CraftSection = {
            storyArc,
            mood
        };

        // ===== OVERALL PROGRESS =====
        const overallProgress = this.calculateOverallProgress(story, understand, craft);

        // ===== NEXT SUGGESTION =====
        const nextSuggestion = this.getNextSuggestion(
            totalSentences, totalTagged, characterCount, chaptersWithEmojis, totalChapters, chapterProgress
        );

        return {
            story,
            understand,
            craft,
            overallProgress,
            nextSuggestion
        };
    }

    private calculateChapterProgress(chapters: Chapter[], sentences: Sentence[]): ChapterProgress[] {
        if (chapters.length === 0) {
            const emojiCount = sentences.filter(s => s.emojis?.length > 0).length;
            return [{
                chapterId: 'all',
                chapterTitle: 'All Content',
                sentenceCount: sentences.length,
                emojiCount,
                percentage: sentences.length > 0 ? Math.round((emojiCount / sentences.length) * 100) : 0
            }];
        }

        return chapters.map(chapter => {
            const chapterSentences = sentences.filter(s => s.chapterId === chapter.id);
            const emojiCount = chapterSentences.filter(s => s.emojis?.length > 0).length;
            const sentenceCount = chapterSentences.length;

            return {
                chapterId: chapter.id,
                chapterTitle: chapter.title || `Chapter ${chapter.index + 1}`,
                sentenceCount,
                emojiCount,
                percentage: sentenceCount > 0 ? Math.round((emojiCount / sentenceCount) * 100) : 0
            };
        });
    }

    private calculateOverallProgress(story: StorySection, understand: UnderstandSection, craft: CraftSection): number {
        let progress = 0;

        // Story foundation (20%)
        if (story.isReady) progress += 20;

        // Understand section (50%)
        if (understand.emojis.status === 'ready') progress += 20;
        else if (understand.emojis.status === 'partial') progress += 10;

        if (understand.characters.status === 'ready') progress += 15;
        if (understand.sentiment.status === 'ready') progress += 15;

        // Craft section (30%)
        if (craft.storyArc.status === 'ready') progress += 15;
        if (craft.mood.status === 'ready') progress += 15;

        return Math.min(100, progress);
    }

    private getNextSuggestion(
        totalSentences: number,
        totalTagged: number,
        characterCount: number,
        chaptersWithEmojis: number,
        totalChapters: number,
        chapterProgress: ChapterProgress[]
    ): string {
        if (totalSentences === 0) {
            return 'Start by writing or pasting your story';
        }

        if (totalSentences < 5) {
            return 'Add a few more sentences to unlock analysis';
        }

        // Priority 1: Generate emojis for chapters that need them
        const needsEmojis = chapterProgress.find(cp => cp.sentenceCount > 0 && cp.percentage < 100);
        if (needsEmojis && totalTagged === 0) {
            return 'Click "Emoji Creation" to start tagging your sentences';
        }

        if (needsEmojis && chaptersWithEmojis < totalChapters) {
            return `Generate emojis for "${needsEmojis.chapterTitle}"`;
        }

        // Priority 2: Define characters after emojis are done
        if (characterCount === 0 && totalTagged > 0) {
            return 'Click "Characters" to define who appears in your story';
        }

        // Priority 3: Explore sentiment analysis
        if (characterCount > 0 && totalSentences >= 5) {
            return 'Check "Sentiment" to see character emotional journeys';
        }

        // Priority 4: Story arc analysis
        if (totalSentences >= 10 && chaptersWithEmojis === totalChapters) {
            return 'View "Story Arc" to analyze narrative structure';
        }

        // Priority 5: Mood analysis
        if (totalSentences >= 8) {
            return 'Explore "Mood" to balance drama, humor, and conflict';
        }

        return 'Great progress! Keep exploring the analysis tools';
    }

    public refreshState(): void {
        const doc = this.documentService.getCurrentDocument();
        const state = this.calculateWorkflowState(doc);
        this.workflowState$.next(state);
    }
}
