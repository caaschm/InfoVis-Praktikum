import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, takeUntil } from 'rxjs';
import { DocumentService } from '../../core/services/document.service';
import { NavigationService } from '../../core/services/navigation.service';
import { ChapterStateService } from '../../core/services/chapter-state.service';
import { DocumentDetail, DocumentMetadata } from '../../core/models/document.model';
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
  activeTab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'storyarc' = 'ai';

  @ViewChild(SidebarComponent) sidebarComponent!: SidebarComponent;

  constructor(
    public documentService: DocumentService,
    private navigationService: NavigationService,
    private chapterStateService: ChapterStateService
  ) { }

  ngOnInit(): void {
    // Subscribe to current document
    this.documentService.currentDocument$
      .pipe(takeUntil(this.destroy$))
      .subscribe(doc => {
        this.currentDocument = doc;
      });

    // Subscribe to navigation events from workflow tracker
    this.navigationService.navigateToTab$
      .pipe(takeUntil(this.destroy$))
      .subscribe(tab => {
        this.onSwitchTab(tab as any);
      });

    // Subscribe to workflow actions
    this.navigationService.workflowAction$
      .pipe(takeUntil(this.destroy$))
      .subscribe(action => {
        this.onWorkflowEffect(action);
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
      // First check if a Sample Story already exists
      this.documentService.listDocuments().subscribe((documents: DocumentMetadata[]) => {
        const existingSample = documents.find((doc: DocumentMetadata) => doc.title === 'Sample Story');

        if (existingSample) {
          // Load the existing Sample Story instead of creating a new one
          this.documentService.loadDocument(existingSample.id).subscribe();
        } else {
          // Only create new Sample Story if none exists
          this.documentService.createDocument(
            'Sample Story',
            'Once upon a time in a distant land, a brave hero embarked on an epic journey. ' +
            'The hero traveled through dark forests and crossed raging rivers. ' +
            'In a mysterious castle, the hero discovered an ancient treasure. ' +
            'A fierce dragon guarded the treasure with flames and fury. ' +
            'The hero fought bravely against the dragon in an epic battle. ' +
            'Magic filled the air as the hero cast powerful spells. ' +
            'A wise wizard appeared and offered guidance to the hero. ' +
            'The dragon finally retreated into the shadows of the castle. ' +
            'The hero claimed the treasure and became a legend. ' +
            'The kingdom celebrated the hero with a grand festival.'
          ).subscribe();
        }
      });
    }
  }

  toggleTab(tab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'storyarc'): void {
    if (this.activeTab === tab && this.sidebarVisible) {
      // Clicking same tab hides sidebar
      this.sidebarVisible = false;
    } else {
      // Clicking different tab shows sidebar with that tab
      this.activeTab = tab;
      this.sidebarVisible = true;
    }
  }

  onSwitchTab(tab: 'emojis' | 'graph' | 'characters' | 'analysis' | 'ai' | 'toc' | 'storyarc'): void {
    // Handle tab switch request from child components (e.g., sidebar)
    this.activeTab = tab;
    this.sidebarVisible = true;
  }

  hideSidebar(): void {
    this.sidebarVisible = false;
  }

  onWorkflowEffect(event: { stepId: string; chapterId?: string; action: string }): void {
    if (event.action === 'generateEmojis' && this.sidebarComponent) {
      if (event.chapterId) {
        // Set the active chapter context FIRST so sidebar knows which chapter to work with
        this.chapterStateService.setActiveChapter(event.chapterId);

        // Then open sidebar and trigger generation
        this.activeTab = 'ai';
        this.sidebarVisible = true;
        if (this.sidebarComponent.generateEmojisForChapter) {
          this.sidebarComponent.generateEmojisForChapter(event.chapterId);
        }
      } else {
        // Generate for all
        this.activeTab = 'ai';
        this.sidebarVisible = true;
        this.sidebarComponent.generateEmojisForAll();
      }
    } else if (event.action === 'Suggest Characters' && this.sidebarComponent) {
      this.activeTab = 'ai';
      this.sidebarVisible = true;
      if (this.sidebarComponent.suggestCharacters) {
        this.sidebarComponent.suggestCharacters();
      }
    } else {
      // No-op or log for other actions
      console.log('Unhandled workflow effect:', event);
    }
  }
}
