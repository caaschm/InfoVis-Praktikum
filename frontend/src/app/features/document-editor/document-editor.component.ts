import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../core/services/document.service';
import { DocumentDetail } from '../../core/models/document.model';
import { TextViewerComponent } from './text-viewer/text-viewer.component';
import { SidebarComponent } from './sidebar/sidebar.component';

@Component({
  selector: 'app-document-editor',
  standalone: true,
  imports: [CommonModule, TextViewerComponent, SidebarComponent],
  templateUrl: './document-editor.component.html',
  styleUrl: './document-editor.component.scss'
})
export class DocumentEditorComponent implements OnInit, OnDestroy {
  currentDocument: DocumentDetail | null = null;
  private destroy$ = new Subject<void>();
  
  // Sidebar management
  sidebarVisible = true;
  activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'storyarc' = 'emojis';

  constructor(public documentService: DocumentService) { }

  ngOnInit(): void {
    // Subscribe to current document
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        this.currentDocument = doc;
      });

    // TODO: For MVP, create a sample document or show upload interface
    // For now, create a sample document
    this.createSampleDocument();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private createSampleDocument(): void {
    // Create sample document if none exists
    if (!this.currentDocument) {
      this.documentService.createDocument(
        'Sample Story',
        'Once upon a time in a distant land. A brave hero embarked on an epic journey. Magic filled the air with wonder.'
      ).subscribe();
    }
  }

  toggleTab(tab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'storyarc'): void {
    if (this.activeTab === tab && this.sidebarVisible) {
      // Clicking same tab hides sidebar
      this.sidebarVisible = false;
    } else {
      // Clicking different tab shows sidebar with that tab
      this.activeTab = tab;
      this.sidebarVisible = true;
    }
  }

  hideSidebar(): void {
    this.sidebarVisible = false;
  }
}
