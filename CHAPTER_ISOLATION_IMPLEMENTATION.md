# Chapter Isolation Implementation

## 🎯 Problem Summary

The editor had chapter support, but chapters were not properly isolated. Text, cursor position, and AI operations were leaking across chapters, causing:
- Text typed in Chapter 1 appearing in Chapter 2
- Cursor position being global instead of per-chapter
- Undo/redo affecting multiple chapters
- AI operations targeting wrong chapters
- Chapter switching causing content loss

## 🏗️ Architectural Solution

### Core Principle: **Chapter Isolation**
Each chapter is treated as a fully isolated text document with:
- Own text content
- Own cursor position
- Own selection range
- Own undo/redo history

### Implementation Components

#### 1. **ChapterStateService** (`chapter-state.service.ts`)
Central service managing per-chapter state:
- **Cursor State**: Tracks cursor position per chapter (sentenceId, offset)
- **Selection State**: Tracks selection range per chapter
- **History**: Per-chapter undo/redo stacks (isolated)
- **Active Chapter**: Tracks which chapter is currently being edited

**Key Methods:**
- `setActiveChapter(chapterId)`: Sets the active chapter (the one being edited)
- `saveCursor(chapterId, sentenceId, offset)`: Saves cursor position
- `getCursor(chapterId)`: Retrieves saved cursor position
- `addHistoryEntry(chapterId, content)`: Adds to chapter's undo history
- `undo(chapterId)` / `redo(chapterId)`: Per-chapter undo/redo

#### 2. **Active Chapter Tracking**
- **Active Chapter** (`activeChapterId`): The chapter currently being edited
- **Selected Chapter** (`selectedChapterId`): The chapter being viewed/filtered (can be null for "All Chapters")
- These are separate concepts:
  - View filter ≠ editing target
  - User can view all chapters but edit one specific chapter

#### 3. **Cursor & Selection Management**
- Cursor position is saved automatically when:
  - User focuses on a sentence (`onSentenceFocus`)
  - User types (`onSentenceInput`)
  - User moves cursor (`onSentenceKeyUp`)
  - User blurs a sentence (`onSentenceBlur`)
- Cursor is restored when switching to a chapter
- Selection is tracked and restored per chapter

#### 4. **Content Updates Scoped to Active Chapter**
- `updateChapterContent()`: New method that updates only a specific chapter's content
- Preserves other chapters' content when updating
- Reconstructs full document in chapter order to help backend preserve assignments

#### 5. **Backend Chapter Assignment Preservation**
- Backend now preserves `chapter_id` when re-parsing document content
- Matches sentences by text to preserve chapter assignments
- For new sentences, infers chapter from context (nearby sentences)
- Maintains chapter boundaries during content updates

#### 6. **AI Operations Scoped to Active Chapter**
- `analyzeDocument()`: Analyzes only active chapter's content
- `applyPreviewText()`: Appends text only to active chapter
- `fetchIntentSuggestions()`: Uses only active chapter's content
- All AI operations check `activeChapterId` before processing

#### 7. **Per-Chapter Undo/Redo**
- Each chapter maintains its own history stack
- Undo in Chapter 1 never affects Chapter 2
- History is isolated and independent per chapter
- TopBarComponent's `goBack()` now uses per-chapter undo

## 🔧 Implementation Details

### Frontend Changes

#### `chapter-state.service.ts` (NEW)
- Manages all per-chapter state
- Provides reactive `activeChapterId$` observable
- Tracks cursor, selection, and history per chapter

#### `text-viewer.component.ts`
- Tracks `activeChapterId` (separate from `selectedChapterId`)
- Saves/restores cursor on chapter switch
- Scopes all sentence updates to active chapter
- Adds focus/keyup handlers to track cursor

#### `document.service.ts`
- Added `updateChapterContent()`: Updates specific chapter while preserving others
- Enhanced `updateDocumentContent()`: Reconstructs content in chapter order

#### `sidebar.component.ts`
- AI analysis uses active chapter's content only
- AI text insertion scoped to active chapter
- Intent suggestions use active chapter context

#### `top-bar.component.ts`
- Undo/redo now uses per-chapter history
- Falls back to global history for backward compatibility

### Backend Changes

#### `routers/documents.py`
- Enhanced `update_document_content()` to preserve `chapter_id`
- Matches sentences by text to preserve chapter assignments
- Infers chapter for new sentences from context
- Maintains chapter boundaries during re-parsing

## 🛡️ Safety Mechanisms

### 1. **Chapter Validation**
- When document updates, validates selected chapter still exists
- Resets to "All Chapters" if selected chapter deleted
- Ensures active chapter is valid

### 2. **Content Preservation**
- `updateChapterContent()` explicitly preserves other chapters
- Reconstructs full document in chapter order
- Backend matches sentences to preserve assignments

### 3. **State Isolation**
- Each chapter's state is completely independent
- No shared state between chapters
- Cursor/selection/history isolated per chapter

### 4. **Backward Compatibility**
- Global undo/redo still works if no active chapter
- AI operations fall back to all content if no active chapter
- Existing features continue to work

## 🎨 Line Numbers (Visual Only)

Line numbers are implemented as:
- Separate DOM layer (`.line-numbers`)
- Visual overlay only
- Never part of text content
- Never sent to AI
- Never affect cursor/indexing
- Generated from `getBodySentences()` which respects chapter filter

## 📝 Chapter Headings

Chapter titles are:
- Part of flowing text structure
- Not used as structural delimiters
- Chapter boundaries handled by data model (`chapterId` on sentences)
- Not parsed from text content

## ✅ Edge Cases Handled

1. **Switching chapters mid-sentence**: Cursor saved, restored on return
2. **AI prompts while cursor idle**: Uses active chapter's cursor context
3. **Editing same sentence in different chapters**: Each chapter has own state
4. **Undo after AI insertion**: Scoped to active chapter only
5. **Viewing all chapters, editing one**: Active chapter tracked separately from view
6. **Fast chapter switching**: State saved/restored efficiently
7. **Emoji generation on selected sentences**: Only targets sentences in active chapter
8. **Cursor restoration after view changes**: Cursor restored when chapter becomes active

## 🚫 What Was NOT Changed

- No existing features removed
- No UI components deleted
- No editor behavior simplified
- All AI features preserved
- All emoji features preserved
- All analytics features preserved
- All existing integrations maintained

## 🔍 Why the Bug Occurred

1. **No Active Chapter Tracking**: System didn't distinguish between "viewing" and "editing" a chapter
2. **Global Cursor State**: Browser's contenteditable cursor was global, not per-chapter
3. **Global Undo/Redo**: Single history stack for entire document
4. **Unscoped AI Operations**: AI operations used entire document content
5. **Content Merging**: Document updates combined all chapters without preserving boundaries
6. **No Chapter Assignment Preservation**: Backend didn't preserve chapter_id during re-parsing

## 🛡️ How the Solution Prevents Regressions

1. **Explicit Active Chapter**: Every operation checks `activeChapterId`
2. **State Service**: Centralized state management prevents leaks
3. **Scoped Updates**: `updateChapterContent()` ensures isolation
4. **Backend Preservation**: Chapter assignments preserved during re-parsing
5. **Validation**: Chapter existence checked on every update
6. **History Isolation**: Per-chapter history prevents cross-chapter undo

## 📊 Data Flow

```
User Action → Set Active Chapter → Save Cursor → Update Content
     ↓
Chapter State Service (isolated state)
     ↓
Document Service (chapter-aware updates)
     ↓
Backend (preserves chapter assignments)
     ↓
Frontend (restores cursor, updates view)
```

## 🎯 Key Architectural Decisions

1. **Separate Active vs Selected Chapter**: Allows viewing all while editing one
2. **Per-Chapter State Service**: Centralized isolation management
3. **Chapter-Aware Content Updates**: Preserves boundaries during updates
4. **Backend Chapter Preservation**: Maintains assignments during re-parsing
5. **Visual-Only Line Numbers**: Never part of content model
6. **Scoped AI Operations**: All AI uses active chapter context

This architecture ensures complete chapter isolation while preserving all existing functionality.
