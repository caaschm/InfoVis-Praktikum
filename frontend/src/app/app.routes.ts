import { Routes } from '@angular/router';
import { DocumentEditorComponent } from './features/document-editor/document-editor.component';


export const routes: Routes = [
    { path: '', component: DocumentEditorComponent },
    { path: 'settings', component: DocumentEditorComponent }, // Test-Route
    { path: '**', redirectTo: '' }
];

