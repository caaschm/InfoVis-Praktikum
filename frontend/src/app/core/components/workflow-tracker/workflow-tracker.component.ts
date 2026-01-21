import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WorkflowTrackerService, WorkflowState, WorkflowStep } from '../../services/workflow-tracker.service';
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

  @Output() navigateToTab = new EventEmitter<string>();
  @Output() executeAction = new EventEmitter<string>();

  constructor(private workflowService: WorkflowTrackerService) {}

  ngOnInit(): void {
    this.workflowState$ = this.workflowService.workflow$;
  }

  toggleExpanded(): void {
    this.isExpanded = !this.isExpanded;
  }

  onStepClick(step: WorkflowStep): void {
    if (step.navigateTo) {
      this.navigateToTab.emit(step.navigateTo);
    }
  }

  onActionClick(step: WorkflowStep, event: Event): void {
    event.stopPropagation();
    if (step.action) {
      this.executeAction.emit(step.id);
    }
  }

  getStatusClass(status: string): string {
    return `status-${status}`;
  }

  getStepTooltip(step: WorkflowStep): string {
    switch (step.status) {
      case 'empty':
        return `${step.label}: Not started yet`;
      case 'partial':
        return `${step.label}: In progress`;
      case 'ready':
        return `${step.label}: Ready ✓`;
      case 'needs-update':
        return `${step.label}: Needs update`;
      default:
        return step.label;
    }
  }
}
