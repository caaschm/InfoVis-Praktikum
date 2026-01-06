# Word Mapping + AI Integration

## 🎯 Overview

The word mapping system now works **both manually and through AI**, with AI respecting manually configured mappings. This gives authors full control while leveraging AI automation.

## 🔄 How It Works

### Manual Mode

1. Author opens **Emojis tab** → clicks **🔤 Word Mappings**
2. Creates mapping: `"dragon" → 🐉`
3. Mapping is saved and marked as active
4. Future AI generations will **always** include 🐉 when "dragon" appears

### AI Mode with Manual Respect

1. Author clicks **Generate Emojis** (single sentence or bulk)
2. Backend loads all active word mappings for the document
3. AI prompt includes: `"IMPORTANT - MUST include these emojis: dragon → 🐉 (REQUIRED)"`
4. Manual emojis are **guaranteed** to appear in the result
5. AI adds additional contextual emojis (mood, actions, etc.)

### Combined Result

```
Text: "The brave dragon flew over the castle"
Manual mappings: dragon → 🐉, castle → 🏰
AI suggestions: 🦅 (flying), ⚔️ (brave)
Final result: 🐉 🏰 🦅 ⚔️
```

## 🏗️ Technical Implementation

### Backend Flow

#### 1. Schema Update (`app/schemas.py`)

```python
class EmojiSuggestionRequest(BaseModel):
    document_id: str
    sentence_id: str
    text: str
    word_mappings: dict[str, str] = {}  # NEW: word → emoji dict
```

#### 2. API Endpoint (`app/routers/ai.py`)

```python
@router.post("/emojis-from-text")
async def suggest_emojis_from_text(request: EmojiSuggestionRequest, db: Session):
    # Load active word mappings from database
    mappings = db.query(models.WordEmojiMapping).filter(
        models.WordEmojiMapping.document_id == sentence.document_id,
        models.WordEmojiMapping.is_active == 1
    ).all()
    word_mappings = {m.word_pattern: m.emoji for m in mappings}
    
    # Pass to AI with manual mappings
    emojis = await generate_emojis_for_sentence(request.text, word_mappings)
    return {"sentence_id": request.sentence_id, "emojis": emojis}
```

#### 3. AI Client (`app/services/ai_client.py`)

```python
async def generate_emojis_for_sentence(text: str, word_mappings: Dict[str, str]):
    # Step 1: Apply manual mappings first
    manual_emojis = []
    text_lower = text.lower()
    for word, emoji in word_mappings.items():
        if word.lower() in text_lower:
            manual_emojis.append(emoji)
            _character_emoji_cache[word.lower()] = emoji  # Cache for consistency
    
    # Step 2: Build AI prompt with manual requirements
    prompt = f"""
    Sentence: "{text}"
    
    IMPORTANT - MUST include these emojis:
    {format_word_mappings(word_mappings)}
    
    Add 2-3 more emojis for mood/action/context.
    """
    
    # Step 3: Call AI
    ai_emojis = await call_openrouter(prompt)
    
    # Step 4: Combine (manual first, then AI, dedupe, max 5)
    combined = list(dict.fromkeys(manual_emojis + ai_emojis))
    return combined[:5]
```

### Frontend Flow

#### 1. Document Service (`document.service.ts`)

```typescript
// New helper method to get word mappings
getCurrentWordMappings() {
  let mappings: any[] = [];
  this.emojiMappingService.wordMappings$.subscribe(m => mappings = m).unsubscribe();
  return mappings;
}

getCurrentSentences(): Sentence[] {
  const doc = this.currentDocumentSubject.value;
  return doc ? doc.sentences : [];
}
```

#### 2. AI Service (`ai.service.ts`)

```typescript
generateEmojisFromText(
  request: EmojiSuggestionRequest, 
  wordMappings?: {[word: string]: string}
): Observable<EmojiSuggestionResponse> {
  // Include word mappings in request body
  const body = wordMappings ? { ...request, word_mappings: wordMappings } : request;
  return this.apiService.post('/api/ai/emojis-from-text', body);
}
```

#### 3. Sidebar Component (`sidebar.component.ts`)

```typescript
private getWordMappingsDict(): {[word: string]: string} {
  const mappings = this.documentService.getCurrentWordMappings();
  const dict: {[word: string]: string} = {};
  mappings.forEach(m => {
    if (m.is_active) {
      dict[m.word_pattern] = m.emoji;
    }
  });
  return dict;
}

generateEmojis(): void {
  const wordMappings = this.getWordMappingsDict();  // Load mappings
  this.aiService.generateEmojisFromText({
    documentId: doc.id,
    sentenceId: this.selectedSentence.id,
    text: this.selectedSentence.text
  }, wordMappings).subscribe(/* ... */);  // Pass to AI
}
```

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Author Creates Manual Mapping                                │
│ "dragon" → 🐉                                                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ POST /api/documents/{id}/emoji-mappings/words                │
│ Stored in database: word_emoji_mappings table                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Author Clicks "Generate Emojis"                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend: Load word mappings from EmojiMappingService        │
│ Convert to dict: {"dragon": "🐉", "castle": "🏰"}           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ POST /api/ai/emojis-from-text                                │
│ Body: { text: "...", word_mappings: {"dragon": "🐉"} }       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend: Check if "dragon" in text.lower()                   │
│ ✓ Found → manual_emojis = ["🐉"]                            │
│ Add to character cache for consistency                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ AI Prompt:                                                    │
│ "Sentence: 'The dragon flew over the castle'                 │
│  IMPORTANT - MUST include: dragon → 🐉 (REQUIRED)           │
│  Add 2-3 more emojis for mood/action"                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ OpenRouter AI Response: ["🐉", "🦅", "🏰", "⚔️"]           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend: Combine & Dedupe                                    │
│ manual_emojis (🐉) + ai_emojis (🦅🏰⚔️)                      │
│ Result: ["🐉", "🦅", "🏰", "⚔️"]                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend: Display emojis in sentence                         │
│ Author sees both manual + AI suggestions                     │
└─────────────────────────────────────────────────────────────┘
```

## 🎨 User Experience

### Before (AI Only)

- AI generates emojis based on mood/plot
- No consistency guarantee
- "dragon" might get 🐲, 🦎, or 🐍 randomly
- Author has to manually fix inconsistencies

### After (Manual + AI Hybrid)

- Author defines: `"dragon" → 🐉` once
- AI **always** includes 🐉 when "dragon" appears
- AI adds **additional** contextual emojis
- Author gets consistency + automation

### Example Workflow

1. **Setup Phase** (Once per document)

```
Author creates mappings:
- dragon → 🐉
- castle → 🏰
- wizard → 🧙‍♂️
- sword → ⚔️
```

1. **Writing Phase** (Continuous)

```
Author writes: "The dragon attacked the castle."
Clicks "Generate Emojis"
Result: 🐉 🏰 💥 ⚔️
  └─ manual ┘  └─ AI ─┘
```

1. **Bulk Generation**

```
Author clicks "Generate Emojis for All Sentences"
ALL sentences with "dragon" get 🐉
ALL sentences with "castle" get 🏰
Consistency across entire document guaranteed!
```

## 🔧 Configuration

### Active/Inactive Mappings

Authors can toggle mappings on/off:

```typescript
// In word-mapping-manager.component
toggleMapping(mapping) {
  mapping.is_active = !mapping.is_active;
  this.emojiMappingService.updateWordMapping(
    documentId, 
    mapping.id, 
    { is_active: mapping.is_active }
  ).subscribe();
}
```

Only `is_active=true` mappings are sent to AI.

### Case Insensitivity

- Stored as lowercase: `"dragon"`
- Matches: "Dragon", "DRAGON", "dragon"
- Backend: `if word.lower() in text.lower()`

### Aliases Support (Future)

Currently: 1 word → 1 emoji
Future: Multiple words → 1 emoji

```json
{
  "word_pattern": "dragon",
  "emoji": "🐉",
  "aliases": ["wyrm", "drake", "wyvern"]  // Coming soon
}
```

## 🧪 Testing

### Test Manual Mapping

1. Create document: "The dragon flew over the castle"
2. Add mapping: `dragon → 🐉`
3. Click "Generate Emojis"
4. ✓ Verify 🐉 is in result

### Test AI Enhancement

1. Same sentence
2. ✓ Verify AI added mood/action emojis (🦅, ⚔️)
3. ✓ Verify total ≤ 5 emojis

### Test Bulk Generation

1. Create document with 10 sentences mentioning "dragon"
2. Add mapping: `dragon → 🐉`
3. Click "Generate Emojis for All Sentences"
4. ✓ Verify all 10 sentences have 🐉

### Test Active/Inactive Toggle

1. Create mapping: `dragon → 🐉`, active=true
2. Generate emojis → ✓ includes 🐉
3. Deactivate mapping
4. Generate emojis → ✗ no 🐉 (only AI suggestions)

## 🚀 Benefits

### For Authors

- **Consistency**: Key terms always get same emoji
- **Control**: Manual mappings override AI randomness
- **Efficiency**: AI fills in mood/context automatically
- **Flexibility**: Toggle mappings on/off per document

### For Readers

- **Visual consistency**: 🐉 always means dragon
- **Better comprehension**: Emojis reinforce meaning
- **Story continuity**: Character emojis stay constant

### For Developers

- **Extensible**: Easy to add character mappings, custom sets
- **Cached**: Character cache prevents API calls
- **Debuggable**: Clear separation: manual vs AI emojis

## 📝 API Reference

### Create Word Mapping

```http
POST /api/documents/{document_id}/emoji-mappings/words
Content-Type: application/json

{
  "word_pattern": "dragon",
  "emoji": "🐉",
  "is_active": true
}
```

### Generate Emojis (with mappings)

```http
POST /api/ai/emojis-from-text
Content-Type: application/json

{
  "document_id": "abc123",
  "sentence_id": "xyz789",
  "text": "The dragon attacked",
  "word_mappings": {
    "dragon": "🐉"
  }
}
```

Response:

```json
{
  "sentence_id": "xyz789",
  "emojis": ["🐉", "⚔️", "🔥"]
}
```

## 🎓 Next Steps

### Immediate

1. ✅ Backend: Load mappings in AI endpoint
2. ✅ Backend: Apply mappings before AI call
3. ✅ Frontend: Pass mappings in AI request
4. ✅ Test integration end-to-end

### Future Enhancements

- [ ] AI-suggested word mappings ("We noticed 'dragon' appears 15 times. Map to 🐉?")
- [ ] Bulk import mappings from JSON/CSV
- [ ] Mapping templates (Fantasy, Sci-Fi, Romance)
- [ ] Emoji usage statistics per word
- [ ] Conflict resolution (2 mappings, same word)
- [ ] Regex patterns (`/king|queen/` → 👑)

## 🐛 Troubleshooting

### Mapping Not Applied

- ✓ Check `is_active=true`
- ✓ Check word appears in text (case-insensitive)
- ✓ Reload document to refresh mappings
- ✓ Check browser console for API errors

### Too Many Emojis

- Manual mappings + AI can exceed 5
- Backend enforces `[:5]` limit
- Manual emojis have priority (added first)

### AI Ignoring Manual Mapping

- Check AI prompt includes "REQUIRED" directive
- Verify `word_mappings` in API request body
- Check backend logs for mapping application

## 📚 Related Documentation

- [ENHANCED_EMOJI_SYSTEM.md](./ENHANCED_EMOJI_SYSTEM.md) - Full system overview
- [INTEGRATION_SUMMARY.md](./INTEGRATION_SUMMARY.md) - UI integration guide
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - Test procedures
