import { Component } from '@angular/core';
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

  constructor(private documentService: DocumentService) { }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const fileName = file.name.replace(/\.[^/.]+$/, ''); // Remove extension

    if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
      this.readTextFile(file, fileName);
    } else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      this.readPdfFile(file, fileName);
    } else {
      alert('Please upload a .txt or .pdf file');
    }

    // Reset input
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
    // For PDF, we'll send to backend for processing
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);

    // Use document service to upload
    this.documentService.uploadPdfDocument(formData).subscribe({
      next: () => console.log('PDF document uploaded'),
      error: (err) => {
        console.error('Error uploading PDF:', err);
        alert('PDF upload is not yet fully supported. Please use .txt files or the backend will need pypdf2 installed.');
      }
    });
  }

  onSettingsClick(): void {
    // TODO: Implement settings functionality
    console.log('Settings clicked');
  }
}
