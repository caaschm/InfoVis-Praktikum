/**
 * Unit test for DocumentService
 * Tests basic state management and observables
 */
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { DocumentService } from './document.service';

describe('DocumentService', () => {
    let service: DocumentService;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [DocumentService]
        });
        service = TestBed.inject(DocumentService);
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should have currentDocument$ observable', (done) => {
        service.currentDocument$.subscribe(doc => {
            expect(doc).toBeNull(); // Initially null
            done();
        });
    });

    it('should have selectedSentence$ observable', (done) => {
        service.selectedSentence$.subscribe(sentence => {
            expect(sentence).toBeNull(); // Initially null
            done();
        });
    });

    it('should be able to get current document', () => {
        const doc = service.getCurrentDocument();
        expect(doc).toBeNull(); // Initially null
    });

    it('should be able to get selected sentence', () => {
        const sentence = service.getSelectedSentence();
        expect(sentence).toBeNull(); // Initially null
    });
});
