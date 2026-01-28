import { Component, OnInit, OnDestroy } from '@angular/core';
import { Location } from '@angular/common';
import { DocumentService } from '../../core/services/document.service';
import { ChapterStateService } from '../../core/services/chapter-state.service';
import { NavigationService } from '../../core/services/navigation.service';
import { CommonModule } from '@angular/common';
import { takeUntil } from 'rxjs/operators';
import { Subject } from 'rxjs';
import { WorkflowTrackerComponent } from '../../core/components/workflow-tracker/workflow-tracker.component';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [CommonModule, WorkflowTrackerComponent, FormsModule],
  templateUrl: './top-bar.component.html',
  styleUrl: './top-bar.component.scss'
})

export class TopBarComponent implements OnInit, OnDestroy {
  appTitle = 'Plottery';
  private historyStack: string[] = []; // Kept for backward compatibility, but per-chapter undo is primary
  showSettingsDropdown = false;
  isColorBlindMode = false;
  isZebraMode = false;
  isLargeFont = false;
  private destroy$ = new Subject<void>();
  public aiModels: string[] = [];
  public selectedModelIndex: number = 0;

  constructor(
    private documentService: DocumentService,
    private chapterStateService: ChapterStateService,
    private navigationService: NavigationService,
    private location: Location,
    private http: HttpClient
  ) { }

  ngOnInit(): void {
    const url = 'http://localhost:8000/ai/get-models'; // Prüfe, ob das Präfix /ai/ stimmt
    console.log('Versuche Modelle zu laden von:', url);

    this.http.get<any>(url).subscribe({
        next: (data) => {
            console.log('Backend Antwort erhalten:', data);
            this.aiModels = data.models || [];
            this.selectedModelIndex = data.current_index || 0;
        },
        error: (err) => {
            console.error('FEHLER beim Laden der Modelle:');
            console.error('Status:', err.status);
            console.error('Message:', err.message);
            console.log('Vollständiger Fehler-Objekt:', err);
            this.aiModels = ["Fallback-Model"];
        }
    });
    this.documentService.currentDocument$.subscribe(doc => {
      if (doc && doc.content) {
        if (this.historyStack.length === 0 || this.historyStack[this.historyStack.length - 1] !== doc.content) {
          this.historyStack.push(doc.content);
        }
      }
    });
  }

  onSettingsClick(): void {
    this.showSettingsDropdown = !this.showSettingsDropdown;
  }

  onModelChange(newModelName: string) {
        // Finde den Index des gewählten Namens
        const index = this.aiModels.indexOf(newModelName);
        if (index === -1) return; // Sicherheitsscheck
        
        // Sende den Index an das Backend
        this.http.post('http://localhost:5000/ai/set-model', { index: index })
            .subscribe((res: any) => {
                this.selectedModelIndex = res.index;
                console.log("Modell erfolgreich auf Server geändert:", res.current_model);
            });
  }

  toggleColorBlindMode(): void {
    this.isColorBlindMode = !this.isColorBlindMode;
    if (this.isColorBlindMode) {
      document.body.classList.add('protanopia-mode');
    } else {
      document.body.classList.remove('protanopia-mode');
    }
    // Optional: Menü nach Auswahl schließen
    // this.showSettingsDropdown = false; 
  }

  toggleZebraMode() {
    this.isZebraMode = !this.isZebraMode;
    if (this.isZebraMode) {
      document.body.classList.add('zebra-mode');
    } else {
      document.body.classList.remove('zebra-mode');
    }
  }

  toggleLargeFont() {
    this.isLargeFont = !this.isLargeFont;
    if (this.isLargeFont) {
      document.body.classList.add('large-font-mode');
    } else {
      document.body.classList.remove('large-font-mode');
    }
  }

  get canUndo(): boolean {
    // Check per-chapter undo first (primary method)
    const activeChapterId = this.chapterStateService.getActiveChapterId();
    if (activeChapterId) {
      return this.chapterStateService.canUndo(activeChapterId);
    }
    // Fallback to global history for backward compatibility
    return this.historyStack.length > 1;
  }

  goBack(): void {
    const currentDoc = this.documentService.getCurrentDocument();
    if (!currentDoc) return;

    // Use per-chapter undo (primary method)
    const activeChapterId = this.chapterStateService.getActiveChapterId();
    if (activeChapterId) {
      const previousContent = this.chapterStateService.undo(activeChapterId);
      if (previousContent !== null) {
        // CRITICAL: Update only the active chapter's content, preserving others
        this.documentService.updateChapterContent(currentDoc.id, activeChapterId, previousContent);
        return;
      }
    }

    // Fallback to global history for backward compatibility
    if (this.historyStack.length > 1) {
      this.historyStack.pop();
      const previousContent = this.historyStack[this.historyStack.length - 1];
      this.documentService.updateDocumentContent(currentDoc.id, previousContent);
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  // ... (onFileSelected, readTextFile, readPdfFile bleiben gleich) ...

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const fileName = file.name.replace(/\.[^/.]+$/, '');
    if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
      this.readTextFile(file, fileName);
    } else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      this.readPdfFile(file, fileName);
    }
    input.value = '';
  }

  private readTextFile(file: File, title: string): void {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (content) {
        this.documentService.createDocument(title, content).subscribe();
      }
    };
    reader.readAsText(file);
  }

  private readPdfFile(file: File, title: string): void {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    this.documentService.uploadPdfDocument(formData).subscribe();
  }

  onWorkflowNavigate(tabId: string): void {
    console.log('Navigate to:', tabId);
    this.navigationService.navigateToTab(tabId as any);
  }

  onWorkflowAction(stepId: string): void {
    console.log('Execute action for:', stepId);
    // TODO: Trigger AI generation based on stepId
    // For now, just open the relevant tab
    this.navigationService.navigateToTab(stepId as any);
  }
}