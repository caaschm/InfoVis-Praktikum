import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WorkflowTrackerService, WorkflowState, WorkflowStep, ChapterProgress } from '../../services/workflow-tracker.service';
import { Observable } from 'rxjs';


@Component({
    selector: 'app-workflow-tracker',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './workflow-tracker.component.html',
    styleUrls: ['./workflow-tracker.component.scss']
})
export class WorkflowTrackerComponent implements OnInit {
    workflowState$!: Observable<WorkflowState>;
    isExpanded = false;
    showChapterDetails = false;

    @Output() navigateToTab = new EventEmitter<string>();
    @Output() executeAction = new EventEmitter<{ stepId: string; chapterId?: string }>();
    @Output() triggerEffect = new EventEmitter<{ stepId: string; chapterId?: string; action: string }>();

    constructor(private workflowService: WorkflowTrackerService) { }

    ngOnInit(): void {
        this.workflowState$ = this.workflowService.workflow$;
    }

    toggleExpanded(): void {
        this.isExpanded = !this.isExpanded;
        if (!this.isExpanded) {
            this.showChapterDetails = false;
        }
    }

    toggleChapterDetails(): void {
        this.showChapterDetails = !this.showChapterDetails;
    }

    onStepClick(step: WorkflowStep): void {
        // If step has an action (like Emoji Creation), trigger it instead of just navigating
        if (step.action) {
            this.triggerEffect.emit({ stepId: step.id, action: step.action });
        }

        // Navigate to the tab
        if (step.navigateTo) {
            this.navigateToTab.emit(step.navigateTo);
            this.isExpanded = false;
        }
    }

    onActionClick(step: WorkflowStep, event: Event, chapterId?: string): void {
        event.stopPropagation();
        if (step.action) {
            this.executeAction.emit({ stepId: step.id, chapterId });
            this.triggerEffect.emit({ stepId: step.id, chapterId, action: step.action });
        }
    }

    getStatusClass(status: string): string {
        return `status-${status}`;
    }

    getProgressColor(percentage: number): string {
        if (percentage === 100) return '#4CAF50';
        if (percentage >= 50) return '#FFB300';
        if (percentage > 0) return '#FF9800';
        return '#e0e0e0';
    }

    trackByChapter(index: number, chapter: ChapterProgress): string {
        return chapter.chapterId;
    }

    onChapterAction(cp: ChapterProgress, event: Event): void {
        event.stopPropagation();
        // Emit with chapterId to generate emojis for just this chapter
        this.triggerEffect.emit({
            stepId: 'emojis',
            chapterId: cp.chapterId,
            action: 'generateEmojis'
        });
    }

    onStoryAction(): void {
        this.navigateToTab.emit('toc');
        this.isExpanded = false;
    }
}
