import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { Chapter } from '../models/document.model';

@Injectable({
  providedIn: 'root'
})
export class ChapterService {
  private apiUrl = `${environment.apiUrl}/api/chapters`;  // Changed from /chapters to /api/chapters

  constructor(private http: HttpClient) { }

  private mapChapterFromApi(apiChapter: any): Chapter {
    return {
      id: apiChapter.id,
      documentId: apiChapter.document_id,
      title: apiChapter.title,
      index: apiChapter.index,
      createdAt: apiChapter.created_at,
      updatedAt: apiChapter.updated_at
    };
  }

  createChapter(documentId: string, title: string): Observable<Chapter> {
    return this.http.post<any>(this.apiUrl, {
      document_id: documentId,
      title: title
    }).pipe(
      map(apiChapter => this.mapChapterFromApi(apiChapter)),
      catchError(error => {
        console.error('Chapter creation error:', error);
        if (error.error) {
          console.error('Error details:', error.error);
        }
        throw error;
      })
    );
  }

  getChapters(documentId: string): Observable<Chapter[]> {
    return this.http.get<any[]>(`${this.apiUrl}/document/${documentId}`).pipe(
      map(apiChapters => apiChapters.map(ch => this.mapChapterFromApi(ch)))
    );
  }

  updateChapter(chapterId: string, title: string): Observable<Chapter> {
    return this.http.patch<any>(`${this.apiUrl}/${chapterId}`, {
      title: title
    }).pipe(
      map(apiChapter => this.mapChapterFromApi(apiChapter))
    );
  }

  deleteChapter(chapterId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${chapterId}`);
  }
}
