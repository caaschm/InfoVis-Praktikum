# Enhanced Emoji System - Feature Documentation

## Overview

The enhanced emoji system gives authors unprecedented control over visual representation in their texts. Instead of just sentence-level emojis, authors can now:

1. **Word-Level Emoji Mappings** - Assign consistent emojis to specific words throughout the document
2. **Custom Emoji Sets** - Curate personalized emoji collections organized by theme or purpose
3. **Character Definitions** - Define recurring characters/subjects with emojis, colors, and aliases
4. **Flexible Emoji Management** - Maintain the existing sentence-level emoji functionality

## Features

### 1. Word-Level Emoji Mappings

**Purpose**: Ensure consistent emoji representation for specific words across your entire document.

**Use Cases**:
- Assign 🐉 to every mention of "dragon"
- Use ⚔️ for "battle" or "fight"
- Represent "magic" with ✨ consistently

**Features**:
- Map any word/phrase to an emoji
- Enable/disable mappings without deleting them
- See suggested words from your document
- Mappings apply automatically when rendering text

**API Endpoints**:
```
GET    /api/documents/{document_id}/emoji-mappings/words
POST   /api/documents/{document_id}/emoji-mappings/words
PATCH  /api/documents/{document_id}/emoji-mappings/words/{mapping_id}
DELETE /api/documents/{document_id}/emoji-mappings/words/{mapping_id}
```

### 2. Custom Emoji Sets

**Purpose**: Organize emojis into thematic collections for quick access.

**Use Cases**:
- "Fantasy Elements" - 🧙‍♂️ 🐉 🏰 ⚔️ 🗡️ 🛡️
- "Character Emotions" - 😊 😢 😡 😱 😍
- "Nature & Weather" - ☀️ 🌙 ⛈️ 🌈 🔥 💧

**Features**:
- Create multiple emoji sets per document
- Mark one set as default for quick access
- Categorized emoji picker (Emotions, Fantasy, Nature, Objects, Animals)
- Visual preview of all emojis in a set

**API Endpoints**:
```
GET    /api/documents/{document_id}/emoji-mappings/sets
POST   /api/documents/{document_id}/emoji-mappings/sets
PATCH  /api/documents/{document_id}/emoji-mappings/sets/{set_id}
DELETE /api/documents/{document_id}/emoji-mappings/sets/{set_id}
```

### 3. Character Definitions

**Purpose**: Define and track recurring characters or subjects with rich metadata.

**Use Cases**:
- Main character "Hero" → 🧙‍♂️ with color #FF5733
- Villain "Dark Lord" → 🧛‍♂️ with aliases ["the shadow", "him"]
- Companion "Unicorn" → 🦄 with description "Loyal magical friend"

**Features**:
- Associate emoji with character name
- Define multiple aliases (alternative names)
- Assign highlight color for text visualization
- Optional description field
- Automatic detection in text

**API Endpoints**:
```
GET    /api/documents/{document_id}/emoji-mappings/characters
POST   /api/documents/{document_id}/emoji-mappings/characters
PATCH  /api/documents/{document_id}/emoji-mappings/characters/{character_id}
DELETE /api/documents/{document_id}/emoji-mappings/characters/{character_id}
```

## Database Schema

### word_emoji_mappings
```sql
- id: string (UUID)
- document_id: string (FK)
- word_pattern: string (case-insensitive)
- emoji: string
- is_active: boolean
- created_at: datetime
```

### custom_emoji_sets
```sql
- id: string (UUID)
- document_id: string (FK)
- name: string
- emojis: text (JSON array)
- is_default: boolean
- created_at: datetime
```

### character_definitions
```sql
- id: string (UUID)
- document_id: string (FK)
- name: string
- emoji: string
- aliases: text (JSON array)
- description: text (optional)
- color: string (hex color, optional)
- created_at: datetime
```

## Frontend Components

### Word Mapping Manager (`word-mapping-manager.component`)
- Word suggestion from document content
- Quick emoji picker
- Enable/disable toggle
- CRUD operations for mappings

### Character Manager (`character-manager.component`)
- Character-specific emoji picker
- Alias management
- Color picker for highlighting
- Description field
- Visual character cards

### Emoji Set Manager (`emoji-set-manager.component`)
- Categorized emoji picker
- Multi-select emoji interface
- Default set marking
- Visual emoji grid display

### Updated Sidebar
- New tabs for each feature
- Clean component-based architecture
- Consistent styling across panels

## Services

### EmojiMappingService
Central service for all enhanced emoji features:
- State management with RxJS BehaviorSubjects
- CRUD operations for all entity types
- Utility methods (getEmojiForWord, getCharactersForWord, etc.)
- Automatic cache management

## Migration

Run the migration script to create new database tables:

```bash
cd backend
python migrate_emoji_features.py
```

## Usage Examples

### Creating a Word Mapping
```typescript
emojiMappingService.createWordMapping(documentId, {
  wordPattern: 'dragon',
  emoji: '🐉',
  isActive: true
}).subscribe();
```

### Creating a Custom Emoji Set
```typescript
emojiMappingService.createCustomSet(documentId, {
  name: 'Fantasy Elements',
  emojis: ['🧙‍♂️', '🐉', '🏰', '⚔️', '🗡️', '🛡️'],
  isDefault: true
}).subscribe();
```

### Creating a Character
```typescript
emojiMappingService.createCharacter(documentId, {
  name: 'Hero',
  emoji: '🧙‍♂️',
  aliases: ['protagonist', 'the chosen one'],
  description: 'Brave warrior on a quest',
  color: '#FF5733'
}).subscribe();
```

## Future Enhancements

Potential additions to further enhance author control:

1. **Phrase-level mappings** - Map multi-word phrases
2. **Contextual mappings** - Different emojis based on context
3. **Emoji sequences** - Combine multiple emojis for complex concepts
4. **Import/export** - Share emoji sets between documents
5. **AI-assisted suggestions** - Suggest word mappings based on content
6. **Visual text overlay** - Show emoji annotations directly on text
7. **Emoji statistics** - Usage analytics and patterns

## Benefits

**For Authors**:
- Fine-grained control over visual representation
- Consistent emoji usage across document
- Reduced emoji selection time
- Creative expression through customization

**For Readers**:
- Consistent visual language
- Enhanced comprehension through symbols
- More engaging reading experience

**For the System**:
- Scalable architecture
- Clean separation of concerns
- Extensible for future features
- Maintains backward compatibility
