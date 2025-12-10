# Quick Start Guide - Enhanced Emoji Features

## Testing the New Features

### 1. Run Database Migration

First, create the new database tables:

```bash
cd backend
python migrate_emoji_features.py
```

### 2. Start Backend

```bash
cd backend
./run_backend.sh
```

### 3. Start Frontend

```bash
cd frontend
npm install  # if not already done
npm start
```

### 4. Test Word-Level Emoji Mappings

1. Open your document in the editor
2. Click the **🔤 Word Mappings** tab on the right sidebar
3. Click **"+ Add Mapping"**
4. Type a word that appears in your text (e.g., "hero", "magic")
5. Select an emoji from the picker
6. Click **"Create Mapping"**
7. Notice the word now has a consistent emoji association

**Try These**:
- Map "dragon" → 🐉
- Map "battle" → ⚔️
- Map "magic" → ✨

### 5. Test Custom Emoji Sets

1. Click the **🎨 Custom Emoji Sets** tab
2. Click **"+ Create Set"**
3. Name your set (e.g., "Fantasy Elements")
4. Click through the category tabs (Emotions, Fantasy, Nature, etc.)
5. Click emojis to add them to your set
6. Check "Set as default" if you want quick access
7. Click **"Create Emoji Set"**

**Suggested Sets**:
- **Character Emotions**: 😊 😢 😡 😱 😍 🤔
- **Fantasy Elements**: 🧙‍♂️ 🐉 🏰 ⚔️ 🗡️ 🛡️ 🪄
- **Nature**: ☀️ 🌙 ⛈️ 🌈 🔥 💧 🌟

### 6. Test Character Definitions

1. Click the **👥 Characters** tab
2. Click **"+ Add Character"**
3. Enter character name (e.g., "Hero", "Villain")
4. Select an emoji
5. Add aliases if character has multiple names
6. Add optional description
7. Select a highlight color
8. Click **"Create Character"**

**Example Characters**:
- **Hero**: 🧙‍♂️, aliases: ["protagonist", "chosen one"], color: #FF5733
- **Villain**: 🧛‍♀️, aliases: ["dark lord", "enemy"], color: #8B00FF
- **Companion**: 🦄, aliases: ["friend", "sidekick"], color: #00CED1

### 7. Test Sentence-Level Emojis (Existing Feature)

1. Click the **😀 Sentence Emojis** tab
2. Click on any sentence in the text viewer
3. Add emojis using the emoji picker
4. Maximum 5 emojis per sentence

## API Testing with curl

### Create Word Mapping
```bash
curl -X POST http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/words \
  -H "Content-Type: application/json" \
  -d '{
    "wordPattern": "dragon",
    "emoji": "🐉",
    "isActive": true
  }'
```

### Create Custom Emoji Set
```bash
curl -X POST http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/sets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fantasy Elements",
    "emojis": ["🧙‍♂️", "🐉", "🏰", "⚔️"],
    "isDefault": true
  }'
```

### Create Character
```bash
curl -X POST http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/characters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hero",
    "emoji": "🧙‍♂️",
    "aliases": ["protagonist"],
    "description": "Main character",
    "color": "#FF5733"
  }'
```

### Get All Mappings
```bash
# Word mappings
curl http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/words

# Custom sets
curl http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/sets

# Characters
curl http://localhost:8000/api/documents/{DOC_ID}/emoji-mappings/characters
```

## Expected Behavior

### Word Mappings
- ✓ Words are mapped case-insensitively ("Dragon" = "dragon")
- ✓ Mappings can be toggled active/inactive
- ✓ Suggested words appear from document content
- ✓ No duplicate word patterns allowed

### Custom Emoji Sets
- ✓ Multiple sets per document
- ✓ Only one default set at a time
- ✓ Emojis organized by category
- ✓ Visual preview of all selected emojis

### Character Definitions
- ✓ Each character has unique name
- ✓ Aliases stored as JSON array
- ✓ Color validation (hex format)
- ✓ Character cards show all metadata

## Troubleshooting

### Backend Issues

**Migration fails:**
```bash
# Reset database and recreate
cd backend
rm plottery.db
python -c "from app.database import init_db; init_db()"
python migrate_emoji_features.py
```

**Router not found:**
- Check `app/main.py` includes `emoji_mappings` router
- Restart backend server

### Frontend Issues

**Components not loading:**
```bash
# Clear Angular cache
cd frontend
rm -rf .angular/
npm start
```

**API calls fail:**
- Check backend is running on port 8000
- Verify CORS is configured in backend
- Check browser console for errors

## Next Steps

Once basic testing is complete:

1. **Integration**: Test how word mappings interact with sentence emojis
2. **Performance**: Test with large documents (100+ sentences)
3. **UI/UX**: Gather feedback on interface usability
4. **Features**: Implement text visualization of mappings
5. **Export**: Add ability to export/import emoji sets

## Demo Scenario

Create a complete story setup:

1. **Document**: Create a fantasy story document
2. **Word Mappings**: 
   - "hero" → 🧙‍♂️
   - "dragon" → 🐉
   - "magic" → ✨
3. **Characters**:
   - "Aria" (Hero) → 🧙‍♀️, #FF5733
   - "Shadowfang" (Dragon) → 🐉, #8B00FF
4. **Emoji Set**: "Fantasy" with 🧙‍♂️ 🐉 🏰 ⚔️ 🗡️ 🛡️ ✨
5. **Sentence Emojis**: Add 2-3 emojis per sentence

This demonstrates the full power of the enhanced emoji system!
