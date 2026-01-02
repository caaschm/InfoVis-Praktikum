import { Component, OnInit } from '@angular/core'; // OnInit hier ergänzt
import { Location } from '@angular/common'; 
import { DocumentService } from '../../core/services/document.service';
import { CommonModule } from '@angular/common'; // Wichtig für *ngIf im Template

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [CommonModule], // CommonModule hinzufügen für *ngIf
  templateUrl: './top-bar.component.html',
  styleUrl: './top-bar.component.scss'
})
export class TopBarComponent implements OnInit {
  appTitle = 'Plottery';
  private historyStack: string[] = [];
  showSettingsDropdown = false;
  isColorBlindMode = false;

  constructor(
    private documentService: DocumentService,
    private location: Location 
  ) { }

  ngOnInit(): void {
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

  get canUndo(): boolean {
    return this.historyStack.length > 1;
  }

  goBack(): void {
    const currentDoc = this.documentService.getCurrentDocument(); 
    if (this.historyStack.length > 1 && currentDoc) {
      this.historyStack.pop(); 
      const previousContent = this.historyStack[this.historyStack.length - 1];
      this.documentService.updateDocumentContent(currentDoc.id, previousContent); 
    }
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
}