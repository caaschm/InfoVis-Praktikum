import { Component } from '@angular/core';
import { Location } from '@angular/common'; // Neu hinzugefügt
import { DocumentService } from '../../core/services/document.service';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [],
  templateUrl: './top-bar.component.html',
  styleUrl: './top-bar.component.scss'
})
export class TopBarComponent {
  appTitle = 'Plottery';
  private historyStack: string[] = [];

  // Wir fügen 'location' einfach im constructor hinzu
  constructor(
    private documentService: DocumentService,
    private location: Location 
  ) { }

  ngOnInit(): void {
    // Die Historie wird hier mitgefilmt
    this.documentService.currentDocument$.subscribe(doc => {
      if (doc && doc.content) {
        if (this.historyStack.length === 0 || this.historyStack[this.historyStack.length - 1] !== doc.content) {
          this.historyStack.push(doc.content);
        }
      }
    });
  }

  get canUndo(): boolean {
  // Der Button soll nur klickbar sein, wenn mehr als ein Zustand im Speicher ist
    return this.historyStack.length > 1;
  }

  goBack(): void {
    const currentDoc = this.documentService.getCurrentDocument(); // Holt das aktuelle Dokument-Objekt
    
    if (this.historyStack.length > 1 && currentDoc) {
      this.historyStack.pop(); // Aktuellen Stand entfernen
      const previousContent = this.historyStack[this.historyStack.length - 1];
      
      // Wir nutzen deine existierende Methode:
      this.documentService.updateDocumentContent(currentDoc.id, previousContent); 
      
      console.log('Inhalt im Backend auf vorherigen Stand zurückgesetzt');
    } else {
      alert('Kein Zurück-Schritt möglich.');
    }
  }


  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const fileName = file.name.replace(/\.[^/.]+$/, ''); 

    if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
      this.readTextFile(file, fileName);
    } else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      this.readPdfFile(file, fileName);
    } else {
      alert('Please upload a .txt or .pdf file');
    }
    input.value = '';
  }

  private readTextFile(file: File, title: string): void {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (content) {
        this.documentService.createDocument(title, content).subscribe({
          next: () => console.log('Document created from txt file'),
          error: (err) => console.error('Error creating document:', err)
        });
      }
    };
    reader.readAsText(file);
  }

  private readPdfFile(file: File, title: string): void {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);

    this.documentService.uploadPdfDocument(formData).subscribe({
      next: () => console.log('PDF document uploaded'),
      error: (err) => {
        console.error('Error uploading PDF:', err);
        alert('PDF upload is not yet fully supported.');
      }
    });
  }

  onSettingsClick(): void {
    console.log('Settings clicked');
  }
}