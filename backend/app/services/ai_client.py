"""AI client for OpenRouter integration."""
import os
from typing import Optional, Dict
import httpx
import json
import re

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🎭 CHARACTER-EMOJI CONSISTENCY MAPPING
# This cache ensures the same character/noun always gets the same emoji
# across different sentences in the document
_character_emoji_cache: Dict[str, str] = {}

def get_api_key() -> str:
    """Get API key dynamically to support hot reload."""
    return os.getenv("OPENROUTER_API_KEY", "")

# Use Mistral's Devstral model - optimized for code and creative tasks
MODEL_NAME = "minimax/minimax-m2-her"


def _extract_character_names(text: str) -> list[str]:
    """🎭 Extract potential character names/nouns from text.
    
    Uses heuristics to find:
    - Capitalized words (likely proper nouns/names)
    - Common role words (hero, villain, king, queen, etc.)
    
    Args:
        text: The sentence text
        
    Returns:
        List of character/noun candidates
    """
    characters = []
    
    # Find capitalized words (but not sentence-initial)
    words = text.split()
    for i, word in enumerate(words):
        # Clean punctuation
        clean_word = re.sub(r'[^\w]', '', word)
        # Capitalized word not at sentence start
        if clean_word and clean_word[0].isupper() and i > 0:
            characters.append(clean_word.lower())
    
    # Common character role keywords
    role_keywords = [
        'hero', 'heroine', 'villain', 'king', 'queen', 'prince', 'princess',
        'knight', 'warrior', 'wizard', 'witch', 'dragon', 'monster',
        'captain', 'general', 'lord', 'lady', 'duke', 'baron',
        'emperor', 'empress', 'commander', 'soldier', 'guard'
    ]
    
    text_lower = text.lower()
    for role in role_keywords:
        if role in text_lower:
            characters.append(role)
    
    return list(set(characters))  # Remove duplicates


async def generate_emojis_for_sentence(text: str, word_mappings: Optional[Dict[str, str]] = None) -> list[str]:
    """
    Generate up to 5 emojis that capture the mood/plot of the given text.
    
    Args:
        text: The sentence text to analyze
        word_mappings: Optional dict of word->emoji mappings to apply (from manual config)
        
    Returns:
        List of 1-5 emoji strings
    """
    word_mappings = word_mappings or {}
    
    # 🎨 First, apply manual word mappings
    manual_emojis = []
    text_lower = text.lower()
    for word, emoji in word_mappings.items():
        if word.lower() in text_lower:
            manual_emojis.append(emoji)
            # Also add to character cache for consistency
            _character_emoji_cache[word.lower()] = emoji
    
    api_key = get_api_key()
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using keyword-based fallback")
        fallback = _keyword_based_emoji_selection(text)
        # Combine manual mappings with fallback, dedupe, limit to 5
        combined = list(dict.fromkeys(manual_emojis + fallback))
        return (combined[:5], {})
    
    print(f"🔑 Using API key: {api_key[:15]}...{api_key[-4:]}")
    print(f"🎨 Manual mappings applied: {manual_emojis}")
    
    # 🎭 Extract characters/nouns for consistency
    characters = _extract_character_names(text)
    
    # 🎭 Build character mapping context (includes manual mappings)
    character_context = ""
    mapped_chars = []
    
    # Add manual word mappings to context
    for word, emoji in word_mappings.items():
        if word.lower() in text_lower:
            mapped_chars.append(f"{word} → {emoji} (REQUIRED)")
    
    # Add existing character cache
    for char in characters:
        if char in _character_emoji_cache and char not in [w.lower() for w in word_mappings.keys()]:
            mapped_chars.append(f"{char} → {_character_emoji_cache[char]}")
    
    if mapped_chars:
        character_context = f"\n\nYou MUST include these mappings:\n" + "\n".join(mapped_chars)
    
    prompt = f"""Analyze this sentence and return emoji mappings in the exact format shown.

Sentence: "{text}"
{character_context}

Return ONLY the mappings, one per line, in this exact format:
phrase:emoji

Rules:
- phrase can be one or multiple words
- emoji must be a single emoji character
- no explanations, no extra text

Example output format:
brave hero:🦸
dragon:🐉
magic castle:🏰"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 50
                }
            )
            
            print(f"📡 OpenRouter response status: {response.status_code}")
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Switching to local fallback.")
                fallback = _keyword_based_emoji_selection(text)
                return (fallback, {})

            if response.status_code != 200:
                print(f"❌ Error response: {response.text}")
                fallback = _keyword_based_emoji_selection(text)
                return (fallback, {})
            
            result = response.json()
            
            # Extract phrase:emoji pairs from response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ AI response: {content}")
            print(f"📝 Parsing emoji mappings from AI response...")
            
            # Parse phrase:emoji format (e.g., "brave hero:🦸\ndragon:🐉")
            # Format: {emoji: [phrase1, phrase2, ...]} - one emoji can represent multiple phrases
            emoji_mappings = {}
            emojis = []
            
            # Clean the response - remove any explanatory text before/after the mappings
            lines = content.strip().split('\n')
            print(f"   Found {len(lines)} lines to parse")
            
            for line in lines:
                line = line.strip()
                print(f"   Parsing line: '{line}'")
                
                if not line or not ':' in line:
                    print(f"     ❌ Skipped - no colon or empty")
                    continue
                    
                parts = line.split(':', 1)
                if len(parts) != 2:
                    print(f"     ❌ Skipped - couldn't split into 2 parts")
                    continue
                    
                phrase = parts[0].strip()
                emoji_part = parts[1].strip()
                
                print(f"     phrase='{phrase}', emoji_part='{emoji_part}'")
                
                # Validate phrase: should be words/letters, not special characters or formatting
                if not phrase or not any(c.isalnum() for c in phrase):
                    print(f"     ❌ Skipped - phrase has no alphanumeric characters")
                    continue
                
                # Skip obvious instruction text
                if phrase.lower().startswith(('example', 'rule', 'note', 'format', 'return', 'output')):
                    print(f"     ❌ Skipped - looks like instruction text")
                    continue
                
                # Extract emoji using regex - match actual emoji characters
                import re
                # Match emoji patterns (including compound emojis with variation selectors and skin tones)
                emoji_pattern = r'[\U0001F300-\U0001F9FF]|[\U0001F600-\U0001F64F]|[\U0001F680-\U0001F6FF]|[\u2600-\u26FF]|[\u2700-\u27BF]'
                emoji_match = re.search(emoji_pattern, emoji_part)
                
                if not emoji_match:
                    # No valid emoji found - skip this line
                    print(f"     ❌ Skipped - no emoji found in '{emoji_part}'")
                    continue
                
                emoji_char = emoji_match.group(0)
                print(f"     ✅ Valid! emoji={emoji_char}, phrase={phrase}")
                
                # Add phrase to this emoji's list
                if emoji_char not in emoji_mappings:
                    emoji_mappings[emoji_char] = []
                    emojis.append(emoji_char)
                emoji_mappings[emoji_char].append(phrase)
            
            if emojis:
                # 🎭 Update character-emoji cache for consistency
                _update_character_emoji_mapping(text, emojis)
                # Return tuple: (emojis list, mappings dict)
                return (emojis[:5], emoji_mappings)
            else:
                print("⚠️  No valid phrase:emoji pairs found, using keyword fallback")
                fallback_emojis = _keyword_based_emoji_selection(text)
                return (fallback_emojis, {})
            
    except Exception as e:
        print(f"❌ Error calling OpenRouter: {type(e).__name__}: {e}")
        fallback = _keyword_based_emoji_selection(text)
        return (fallback, {})


def _update_character_emoji_mapping(text: str, emojis: list[str]) -> None:
    """🎭 Update character-emoji cache for consistency.
    
    Maps detected characters to their emojis so future sentences
    use the same emoji for the same character.
    
    Args:
        text: The sentence text
        emojis: List of emojis generated for this sentence
    """
    characters = _extract_character_names(text)
    
    # Map each new character to an emoji (prioritize people/creature emojis)
    # List of known character-related emojis
    known_character_emojis = ['👑', '⚔️', '🏰', '🦸', '🦹', '👼', '😈', '👻', '🧙', '🧚', '🧛', '🧜']
    
    people_creature_emojis = []
    for e in emojis:
        # Check if it's a known character emoji
        if e in known_character_emojis:
            people_creature_emojis.append(e)
            continue
        # Try to check Unicode range for single-codepoint emojis
        try:
            if len(e) == 1:
                code = ord(e)
                if (code in range(0x1F600, 0x1F650) or 
                    code in range(0x1F400, 0x1F4D0)):
                    people_creature_emojis.append(e)
        except (TypeError, ValueError):
            # Skip emojis we can't process
            pass
    
    emoji_idx = 0
    for char in characters:
        if char not in _character_emoji_cache and emoji_idx < len(people_creature_emojis):
            _character_emoji_cache[char] = people_creature_emojis[emoji_idx]
            print(f"🎭 Character mapping: '{char}' → {people_creature_emojis[emoji_idx]}")
            emoji_idx += 1


def get_character_emoji_mappings() -> Dict[str, str]:
    """🎭 Get current character-emoji mappings for debugging/display.
    
    Returns:
        Dictionary mapping character names to their assigned emojis
    """
    return _character_emoji_cache.copy()


def clear_character_emoji_mappings() -> None:
    """🎭 Clear character-emoji cache (e.g., when starting new document)."""
    global _character_emoji_cache
    _character_emoji_cache = {}
    print("🎭 Character-emoji cache cleared")


def _keyword_based_emoji_selection(text: str) -> list[str]:
    """
    Generate up to 5 emojis that capture the mood/plot of the given text.
    
    Args:
        text: The sentence text to analyze
        
    Returns:
        List of 1-5 emoji strings
    """
    # Use keyword-based emoji selection as fallback (free models are often rate-limited)
    text_lower = text.lower()
    emojis = []
    
    # Emotion keywords
    if any(word in text_lower for word in ['happy', 'joy', 'glad', 'excited', 'wonderful', 'great']):
        emojis.append('😊')
    if any(word in text_lower for word in ['sad', 'cry', 'tear', 'depressed', 'miserable']):
        emojis.append('😢')
    if any(word in text_lower for word in ['angry', 'mad', 'furious', 'rage', 'hate']):
        emojis.append('😠')
    if any(word in text_lower for word in ['love', 'heart', 'adore', 'romance']):
        emojis.append('❤️')
    if any(word in text_lower for word in ['scared', 'fear', 'afraid', 'terror', 'horror']):
        emojis.append('😱')
    if any(word in text_lower for word in ['laugh', 'funny', 'hilarious', 'joke']):
        emojis.append('😂')
    
    # Story elements
    if any(word in text_lower for word in ['magic', 'spell', 'wizard', 'witch', 'enchant']):
        emojis.append('✨')
    if any(word in text_lower for word in ['fight', 'battle', 'sword', 'warrior', 'combat']):
        emojis.append('⚔️')
    if any(word in text_lower for word in ['king', 'queen', 'prince', 'princess', 'royal', 'crown']):
        emojis.append('👑')
    if any(word in text_lower for word in ['dragon', 'monster', 'beast']):
        emojis.append('🐉')
    if any(word in text_lower for word in ['lion', 'tiger', 'leopard']):
        emojis.append('🦁')
    if any(word in text_lower for word in ['wolf', 'wolves']):
        emojis.append('🐺')
    if any(word in text_lower for word in ['bear']):
        emojis.append('🐻')
    if any(word in text_lower for word in ['castle', 'palace', 'tower']):
        emojis.append('🏰')
    if any(word in text_lower for word in ['book', 'read', 'story', 'tale', 'write']):
        emojis.append('📖')
    if any(word in text_lower for word in ['night', 'dark', 'moon', 'midnight']):
        emojis.append('🌙')
    if any(word in text_lower for word in ['sun', 'bright', 'day', 'morning']):
        emojis.append('☀️')
    if any(word in text_lower for word in ['star', 'shine', 'sparkle']):
        emojis.append('⭐')
    if any(word in text_lower for word in ['fire', 'flame', 'burn']):
        emojis.append('🔥')
    if any(word in text_lower for word in ['water', 'ocean', 'sea', 'river']):
        emojis.append('💧')
    if any(word in text_lower for word in ['hero', 'brave', 'courageous']):
        emojis.append('🦸')
    if any(word in text_lower for word in ['villain', 'evil', 'dark']):
        emojis.append('🦹')
    if any(word in text_lower for word in ['death', 'die', 'dead', 'kill']):
        emojis.append('💀')
    if any(word in text_lower for word in ['angel', 'heaven', 'divine']):
        emojis.append('👼')
    if any(word in text_lower for word in ['demon', 'devil', 'hell']):
        emojis.append('😈')
    if any(word in text_lower for word in ['ghost', 'spirit', 'haunt']):
        emojis.append('👻')
    if any(word in text_lower for word in ['unicorn', 'magical', 'mystical']):
        emojis.append('🦄')
    
    # If we found emojis, return up to 5
    if emojis:
        return emojis[:5]
    
    # Default fallback
    return ['📝', '✨', '📖']


async def generate_text_from_emojis(
    emojis: list[str],
    context: Optional[str] = None
) -> str:
    """
    Generate 1-2 sentences that match the given emojis and optional context.
    
    Args:
        emojis: List of 1-5 emojis representing the desired mood/plot
        context: Optional surrounding text for better context
        
    Returns:
        Generated text (1-2 sentences)
    """
    api_key = get_api_key()
    
    if not api_key:
        return f"A mysterious figure emerged from the shadows. {' '.join(emojis)}"
    
    emoji_str = " ".join(emojis)
    context_part = f"\n\nContext from the story:\n{context}" if context else ""

    prompt = f"""Generate 1-2 sentences for a creative story that match these emojis: {emoji_str}

The emojis represent the mood, emotion, and plot direction.{context_part}

Write naturally as part of a story:"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a creative writing assistant. Generate engaging story sentences."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.8,
                    "max_tokens": 100
                }
            )
            response.raise_for_status()
            result = response.json()
            
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return text if text else f"A mysterious figure emerged from the shadows. {emoji_str}"
            
    except Exception as e:
        # Check specifically for rate limit in exception message if raised by status check
        if "429" in str(e) or (hasattr(e, "response") and e.response.status_code == 429):
             print(f"⚠️ OpenRouter free tier limit reached (429). Using fallback text.")
        else:
             print(f"Error generating text: {e}")
        return f"A mysterious figure emerged from the shadows. {emoji_str}"


def check_api_key_configured() -> bool:
    """Check if the OpenRouter API key is configured."""
    return bool(get_api_key())


async def analyze_spider_chart_values(text: str) -> dict[str, int]:
    """
    Analyze text using AI to scan through and rate sentiment/mood dimensions.
    The AI directly analyzes the text and rates it on drama, humor, conflict, and mystery.
    
    Args:
        text: The text to analyze (can be full document or selected portion)
        
    Returns:
        Dictionary with keys: drama, humor, conflict, mystery (values 0-100)
    """
    api_key = get_api_key()
    print("🔑 OPENROUTER_API_KEY present?", bool(api_key))
    print("🔑 OPENROUTER_API_KEY (gekürzt):", api_key[:8], "...", api_key[-4:])
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using simple fallback")
        return _simple_fallback_analysis(text)
    
    prompt = f"""Scan through this text and analyze its emotional tone and mood. Rate it on four dimensions (0-100 scale):

- Drama: Emotional intensity, tension, high stakes, deep feelings, tragic moments
- Humor: Lightheartedness, comedy, wit, amusing situations, playful moments
- Conflict: Disagreements, battles, opposition, struggles, anger, hostility, confrontations
- Mystery: Unanswered questions, secrets, intrigue, puzzles, hidden elements, uncertainty

Text to analyze:
"{text}"

Carefully read the entire text and choose appropriate values for each dimension
based on how strongly it appears in the story.

Respond with ONLY a JSON object with integer values between 0 and 100, for example:
{{"drama": 72, "humor": 15, "conflict": 60, "mystery": 40}}

Do NOT copy the example numbers. Compute new values that best fit the given text.
No explanations, no markdown, just the JSON object."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Lower temperature for more consistent analysis
                    "max_tokens": 150
                }
            )
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Using neutral analysis.")
                return _simple_fallback_analysis(text)

            if response.status_code != 200:
                print(f"❌ Error response: {response.text}")
                return _simple_fallback_analysis(text)
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print("🧠 RAW AI RESPONSE:", content)

            # Try to extract JSON from response
            # Remove markdown code blocks if present
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            content = content.strip()
            
            try:
                analysis = json.loads(content)
                # Validate and clamp values
                return {
                    "drama": max(0, min(100, int(analysis.get("drama", 50)))),
                    "humor": max(0, min(100, int(analysis.get("humor", 50)))),
                    "conflict": max(0, min(100, int(analysis.get("conflict", 50)))),
                    "mystery": max(0, min(100, int(analysis.get("mystery", 50))))
                }
            except json.JSONDecodeError:
                print(f"⚠️  Could not parse JSON from response: {content}")
                return _simple_fallback_analysis(text)
            
    except Exception as e:
        print(f"❌ Error calling OpenRouter: {type(e).__name__}: {e}")
        return _simple_fallback_analysis(text)


def _simple_fallback_analysis(text: str) -> dict[str, int]:
    """
    Simple fallback when AI is unavailable - returns heuristic values based on simple keyword matching.
    
    Args:
        text: The text to analyze
        
    Returns:
        Dictionary with estimated drama, humor, conflict, mystery values (0-100)
    """
    text_lower = text.lower()
    
    # Enhanced keyword lists
    keywords = {
        "drama": [
            'love', 'cry', 'sad', 'tear', 'heart', 'feel', 'emotion', 'tragic', 'loss', 'hope', 
            'despair', 'life', 'death', 'pain', 'broken', 'soul', 'darkness', 'alone', 'miss', 
            'regret', 'sorry', 'please', 'wait', 'leave', 'hurt', 'feelings', 'moment', 'touch',
            'eyes', 'voice', 'whisper', 'scream', 'fear', 'scared', 'afraid', 'worry', 'anxious'
        ],
        "humor": [
            'laugh', 'funny', 'joke', 'smile', 'happy', 'fun', 'joy', 'silly', 'wit', 'comedy', 
            'haha', 'giggle', 'lol', 'crazy', 'stupid', 'dumb', 'clumsy', 'trip', 'fall', 
            'oops', 'awkward', 'weird', 'strange', 'grin', 'chuckle', 'snort', 'play', 'game',
            'ridiculous', 'absurd', 'hilarious', 'amusing', 'entertaining', 'cheerful'
        ],
        "conflict": [
            'fight', 'war', 'battle', 'kill', 'attack', 'enemy', 'hate', 'anger', 'hurt', 'wound', 
            'blood', 'sword', 'gun', 'argue', 'shout', 'yell', 'scream', 'punch', 'kick', 'beat',
            'destroy', 'break', 'smash', 'crush', 'rival', 'opponent', 'danger', 'threat', 'risk',
            'tension', 'stress', 'pressure', 'force', 'power', 'strength', 'resist', 'defend'
        ],
        "mystery": [
            'secret', 'hide', 'dark', 'shadow', 'unknown', 'question', 'clue', 'strange', 'weird', 
            'ghost', 'magic', 'whisper', 'fog', 'mist', 'night', 'moon', 'stars', 'silent', 
            'quiet', 'hush', 'sneak', 'creep', 'search', 'find', 'discover', 'reveal', 'truth',
            'lie', 'puzzle', 'riddle', 'maze', 'trap', 'lost', 'confused', 'wonder', 'curious'
        ]
    }
    
    scores = {}
    total_words = len(text_lower.split())
    if total_words == 0:
        return {"drama": 50, "humor": 50, "conflict": 50, "mystery": 50}
        
    for cat, words in keywords.items():
        count = sum(1 for word in words if word in text_lower)
        
        # Scoring logic: 
        # Base score 35 (mildly present)
        # Each match adds significant points to ensure visibility
        # Cap at 95
        score = 35 + (count * 8)
        
        # If words are present but score is low, minimal 55 to show "Something"
        if count > 0:
            score = max(55, score)
            
        scores[cat] = min(95, max(10, score))
        
    return scores

async def generate_spider_intent(text: str, dimension: str, baseline: int, current: int):
    api_key = get_api_key()

    if not api_key:
        return {
            "summary": "No AI available.",
            "ideas": ["Try adjusting details in the scene.", "Consider emotional pacing.", "Edit character motivations."],
            "preview": ""
        }

    direction = "increase" if current > baseline else "decrease"
    difference = abs(current - baseline)
    target_value = current  # The value the user moved the slider to

    dim_labels = {
        "drama": "Drama (emotional intensity, high stakes, depth of feeling)",
        "humor": "Humor (lightheartedness, comedy, playful tone)",
        "conflict": "Conflict (opposition, tension, disagreement, obstacles)",
        "mystery": "Mystery (secrets, questions, hidden motives, intrigue)"
    }

    label = dim_labels.get(dimension, dimension.capitalize())

    # If the user moved the slider towards 100%, suggest how to reach 100%
    if current > baseline:
        goal_text = f"reach {target_value}% (and ideally 100%)"
        goal_instruction = f"to increase {dimension} to {target_value}% or even 100%"
    else:
        goal_text = f"reduce to {target_value}%"
        goal_instruction = f"to decrease {dimension} to {target_value}%"

    prompt = f"""
You are helping a fiction writer adjust their story's tone.

The writer moved the slider for **{label}** from {baseline}% to {target_value}%.
They want to {goal_instruction} in their story.

Give concise, actionable suggestions:

1. **SUMMARY** (keep brief, 1 sentence): What reaching {goal_text} for {label} means.

2. **IDEAS** (exactly 3, each max 10 words): Short, specific actions like "Add witty dialogue" or "Include dramatic revelation". Be direct and actionable.

3. **PREVIEW** (one short sentence, max 15 words): Example sentence showing the desired tone.

Current story text:
\"\"\"{text}\"\"\"


Respond ONLY in valid JSON format. Do not add any conversational text before or after the JSON.
{{
  "summary": "...",
  "ideas": ["...", "...", "..."],
  "preview": "..."
}}

IMPORTANT: The "preview" field MUST contain a creative, complete sentence reflecting the requested change. It cannot be empty.
"""

    try:
        # Try primary model, then fallback to backup
        models_to_try = [
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-2.0-flash-thinking-exp:free", 
            "meta-llama/llama-3.3-70b-instruct:free",
            "microsoft/phi-4:free",
            "google/gemini-2.0-flash-001"
        ]
        
        last_exception = None
        
        for model in models_to_try:
            print(f"🔄 Attempting generation with model: {model}")
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    res = await client.post(
                        OPENROUTER_API_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:4200",
                            "X-Title": "Story Writing Assistant"
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 300,
                        },
                    )

                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"].strip()
                    print(f"✅ Success with {model}")
                    break # Success!
                elif res.status_code == 429:
                    print(f"⚠️ Rate limit (429) with {model}. Likely account-wide limit.")
                    # Break the loop to trigger fallback immediately, no point trying other models on same account
                    break
                else:
                    print(f"⚠️ Failed with {model}: Status {res.status_code}")
                    last_exception = Exception(f"Status {res.status_code}: {res.text}")
                    continue # Try next model
            except Exception as e:
                print(f"⚠️ Error with {model}: {e}")
                last_exception = e
                continue
        
        if 'raw' not in locals():
            print("⚠️ All AI models failed. Using local heuristic fallback.")
            
            # Local fallback based on dimension
            dim_key = dimension.lower()
            
            fallback_sentences = {
                "drama": [
                    "The silence stretched on, heavy with unsaid words and lingering regret.",
                    "Tears welled in her eyes as the realization of what she had lost finally hit home.",
                    "It was a moment that would change everything, a turning point from which there was no return."
                ],
                "humor": [
                    "He tripped over his own feet, sending the tray of drinks flying in a spectacular arc.",
                    "She couldn't help but giggle at the absurdity of the situation.",
                    "It was the kind of mistake that would be funny in ten years, but right now, it was just chaotic."
                ],
                "conflict": [
                    "Their voices rose in anger, echoing off the stone walls of the chamber.",
                    "Steel met steel with a deafening clang as the duel began in earnest.",
                    "There could be no peace between them now, not after what had been said."
                ],
                "mystery": [
                    "In the shadows, something watched and waited for the perfect moment to strike.",
                    "The note was unsigned, but the handwriting felt disturbingly familiar.",
                    "A cold draft swept through the room, extinguishing the candles one by one."
                ]
            }
            
            # Dimension-specific advice (instead of generic error messages)
            fallback_advice = {
                "drama": [
                    "Focus on the character's internal reaction.",
                    "Slow down the pacing to emphasize importance.",
                    "Use sensory details to heighten emotion."
                ],
                "humor": [
                    "Subvert expectations with a sudden twist.",
                    "Use exaggeration to highlight absurdity.",
                    "Focus on a character's embarrassing reaction."
                ],
                "conflict": [
                    "Shorten sentences to increase tension.",
                    "Focus on the physical sensations of anger/fear.",
                    "Make the stakes personal for the character."
                ],
                "mystery": [
                    "Reveal a clue but hide its meaning.",
                    "Use lighting or atmosphere to create unease.",
                    "End the sentence with an unanswered question."
                ]
            }

            import random
            preview_text = random.choice(fallback_sentences.get(dim_key, ["The story took an unexpected turn."]))
            advice_list = fallback_advice.get(dim_key, ["Vary sentence length.", "Show, don't tell.", "Use strong verbs."])
            
            return {
                "summary": f"Increasing {dim_key} (Offline Mode)",
                "ideas": advice_list,
                "preview": preview_text
            }

        # raw is already set in the loop

        print(f"DEBUG: Raw AI Intent Response: {raw}")

        # Robust JSON extraction: look for the first '{' and the last '}'
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)
            else:
                cleaned = raw  # Fallback to raw if no braces found (unlikely to work but worth a try)
            
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error: {e} | Cleaned Text: {cleaned}")
            raise e

    except Exception as e:
        print(f"❌ Error generating spider intent: {type(e).__name__}: {e}")
        return {
            "summary": "AI Service Unavailable",
            "ideas": ["Focus on sensory details.", "Show specific character reactions.", "Vary sentence rhythm."],
            "preview": "Service is currently unavailable. Please try again later."
        }

# Called by ai.py --> compute_story_arc to generate beat data for visualization of the story arc
# Beats are important for the arc visualization and must always include all five stages
# Returns dict with "beats": [beat dicts]
async def generate_beats_for_arc(text: str) -> dict:
    api_key = get_api_key()
    STAGES = ["Exposition", "Rising Action", "Climax", "Falling Action", "Denouement"]

    # Default structure: ALL stages exist
    beats = [
        {"name": stage, "position": i / (len(STAGES) - 1), "note": "", "value": 0.0}
        for i, stage in enumerate(STAGES)
    ]

    # No API key --> return flat zero arc with visible stage points
    if not api_key:
        return {
            "beats": beats
        }
    
    # For correct sentence index: Split text into sentences like in ai.py
    text = text.replace("\n", " ").strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s for s in sentences if s]

    # Create numbered text
    numbered_text = "\n".join(f"{i}: {s}" for i, s in enumerate(sentences))

    prompt = f"""
        Analyze the following text and map it onto a fixed five-stage narrative structure.

        STAGES (fixed order, all must be present): {STAGES}

        CORE CONCEPT:
        The numeric "value" represents RELATIVE narrative tension within THIS story.
        Tension values must be scaled internally so that the MOST intense moment in the text has the highest value.

        CRITICAL RULES (VERY IMPORTANT):

        1. Every stage MUST be included in the output.
        If no suitable sentence exists for a stage:
        - note MUST be an empty string
        - value MUST be exactly 0.0

        2. CLIMAX RULE (MANDATORY):
        - If a Climax exists (value > 0), it MUST be the single highest value of all stages.
        - No other stage may have a value equal to or higher than the Climax.
        - Exposition and Rising Action MUST have lower values than the Climax.

        3. ORDERED TENSION RULE:
        - Exposition tension should be low.
        - Rising Action tension may increase.
        - Climax represents the peak of tension.
        - Falling Action must decrease after the Climax.
        - Denouement must be low or zero.

        4. If NO Climax sentence exists:
        - Climax.value MUST be 0.0
        - Rising Action may be the highest non-zero value
        - Do NOT imply or invent a climax.

        5. Values must be between 0.0 and 1.0 and represent relative intensity,
        not absolute drama or genre expectations.

        6. Notes:
        - If a stage has a value > 0, note MUST be a short paraphrase (max 20 words)
            of the specific sentence that justifies the tension.
        - If value == 0, note MUST be empty.

        7. Sentence_index:
        - The index of the sentence in the original text list that represents the note.
        - If no sentence exists, set sentence_index to null and value to 0.0

        Return EXACTLY this JSON format and nothing else:

        {{
        "beats": [
            {{"name": "Exposition", "note": "", "value": 0.0, "sentence_index": null}},
            {{"name": "Rising Action", "note": "", "value": 0.0, "sentence_index": null}},
            {{"name": "Climax", "note": "", "value": 0.0, "sentence_index": null}},
            {{"name": "Falling Action", "note": "", "value": 0.0, "sentence_index": null}},
            {{"name": "Denouement", "note": "", "value": 0.0, "sentence_index": null}}
        ]
        }}

        Text: {numbered_text}

        - Use the sentence number before each sentence as the sentence_index (0-based).
        - Do NOT create new sentences or split them differently.
        - The text is numbered and must be used exactly as provided.
        """

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 400,
                    "response_format": {"type": "json_object"}
                },
            )

        # Check HTTP status code first
        if res.status_code == 429:
            print("⚠️ OpenRouter rate limit (429). Using fallback beats.")
            return {"beats": beats}
        
        if res.status_code != 200:
            print(f"❌ API error {res.status_code}: {res.text[:200]}")
            return {"beats": beats}

        response_data = res.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            # Delete possible ```json Blocks
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content).strip()
            
            if not content:
                print("⚠️ Empty content from API response")
                return {"beats": beats}
            
            # Extract only the valid JSON object (handles extra text before/after and duplicate braces)
            # Find first { and match it with its closing }
            start_idx = content.find('{')
            if start_idx == -1:
                print(f"⚠️ No JSON object found in response. Content: {content}")
                return {"beats": beats}
            
            # Find matching closing brace by counting
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx == -1:
                print("⚠️ Malformed JSON in response - could not find matching closing brace")
                return {"beats": beats}
            
            json_str = content[start_idx:end_idx+1]
            
            # Parse JSON
            try:
                parsed = json.loads(json_str)
                print("Raw AI response for story arc:", parsed)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parse error: {e}")
                print(f"Content: {json_str[:200]}")
                return {"beats": beats}
        else:
            raise Exception(f"No 'choices' in response: {response_data}")

        ai_beats = parsed.get("beats", [])

        # Merge AI results into fixed beat structure
        for i, stage in enumerate(STAGES):
            for b in ai_beats:
                if b.get("name") == stage:
                    beats[i]["note"] = b.get("note", "")
                    beats[i]["value"] = float(b.get("value", 0.0))
                    beats[i]["sentence_index"] = b.get("sentence_index")
                    break

        return {"beats": beats}

    except Exception as e:
        print("❌ Story arc error:", e)
        return {
            "beats": beats
        }


async def reformulate_sentence_for_tension(text: str, tension_value: float) -> str:
    """
    Reformulate a sentence to match a specific tension value (0.0 to 1.0).
    
    Args:
        text: The original sentence text
        tension_value: Target tension value (0.0 = low tension, 1.0 = high tension)
        
    Returns:
        Reformulated sentence text matching the target tension
    """
    api_key = get_api_key()
    
    if not api_key:
        return text  # Return original if no API key
    
    # Convert tension value to descriptive terms
    if tension_value < 0.2:
        tension_desc = "very low tension, calm, peaceful"
    elif tension_value < 0.4:
        tension_desc = "low tension, relaxed, gentle"
    elif tension_value < 0.6:
        tension_desc = "moderate tension, balanced, steady"
    elif tension_value < 0.8:
        tension_desc = "high tension, intense, dramatic"
    else:
        tension_desc = "very high tension, extreme, climactic"
    
    tension_percent = int(tension_value * 100)
    
    prompt = f"""Rewrite the following sentence to match a tension level of {tension_percent}% ({tension_desc}).

The tension value represents narrative intensity:
- Low (0-40%): Calm, peaceful, relaxed, gentle moments
- Moderate (40-60%): Balanced, steady, normal pacing
- High (60-80%): Intense, dramatic, suspenseful moments
- Very High (80-100%): Extreme, climactic, peak tension moments

Original sentence: "{text}"

Rewrite the sentence to match {tension_percent}% tension while:
1. Keeping the same core meaning and story content
2. Adjusting word choice, sentence structure, and pacing to match the tension level
3. Maintaining natural, readable prose
4. Preserving character names and key plot elements

Respond with ONLY the rewritten sentence. No explanations, no quotes, just the sentence itself."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 150
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Error response: {response.text}")
                return text
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Remove quotes if present
            content = content.strip('"').strip("'").strip()
            
            return content if content else text
            
    except Exception as e:
        print(f"❌ Error reformulating sentence: {type(e).__name__}: {e}")
        return text


async def generate_chapter_title(chapter_content: str, chapter_type: str = "chapter") -> str:
    """
    Generate a title suggestion for a chapter based on its content.
    
    Args:
        chapter_content: The full text content of the chapter
        chapter_type: Type of section (chapter, prologue, epilogue, etc.)
        
    Returns:
        Suggested title string
    """
    api_key = get_api_key()
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using fallback title")
        return _fallback_title_suggestion(chapter_content)
    
    # Determine section type context
    type_context = {
        "chapter": "a numbered chapter",
        "prologue": "a prologue",
        "epilogue": "an epilogue",
        "interlude": "an interlude",
        "foreword": "a foreword",
        "afterword": "an afterword",
        "custom": "a custom section"
    }
    section_type_desc = type_context.get(chapter_type, "a chapter")
    
    prompt = f"""You are helping a fiction writer create a title for {section_type_desc}.

Read the following chapter content and suggest a compelling, concise title (2-5 words) that captures the essence, main event, or key theme of this section.

Chapter content:
"{chapter_content}"

Rules:
- The title should be 2-5 words maximum
- It should be evocative and capture the main theme or key event
- For numbered chapters, suggest only the title part (without the number)
- Make it engaging and memorable
- If the content is very short or unclear, suggest a generic but fitting title

Respond with ONLY the title, no explanations, no quotes, no numbering. Just the title words.

Example outputs:
- "The Dragon's Lair"
- "First Encounter"
- "Revelation"
- "Journey Begins"
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.8,
                    "max_tokens": 30
                }
            )
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Using fallback title.")
                return _fallback_title_suggestion(chapter_content)
            
            if response.status_code != 200:
                print(f"❌ Error generating title: {response.text}")
                return _fallback_title_suggestion(chapter_content)
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Clean up the response - remove quotes, extra whitespace
            title = re.sub(r'^["\']|["\']$', '', content).strip()
            # Remove any numbering if present
            title = re.sub(r'^\d+[\.\s]+', '', title).strip()
            
            if not title:
                return _fallback_title_suggestion(chapter_content)
            
            return title
            
    except Exception as e:
        print(f"Error generating chapter title: {e}")
        return _fallback_title_suggestion(chapter_content)


def _fallback_title_suggestion(content: str) -> str:
    """Simple fallback title suggestion based on keywords."""
    if not content or len(content.strip()) < 10:
        return "Untitled"
    
    content_lower = content.lower()
    
    # Extract first significant words or key themes
    words = content.split()[:10]
    significant_words = [w for w in words if len(w) > 4 and w.lower() not in ['the', 'this', 'that', 'with', 'from', 'into']]
    
    if significant_words:
        # Use first significant word or phrase
        return significant_words[0].capitalize()
    
    # Fallback to first word
    return words[0].capitalize() if words else "Untitled"


async def analyze_character_pattern(
    text: str,
    character_name: str,
    character_aliases: list[str] = None
) -> str:
    """
    Detect typical narrative role/pattern for the character (hero, villain, mentor, sidekick, neutral).
    Used to give sentiment analysis narrative context (e.g. hero defeating threat = positive; villain being defeated = negative).
    """
    api_key = get_api_key()
    character_aliases = character_aliases or []
    search_terms = [character_name.lower()] + [a.lower() for a in character_aliases]
    terms_str = ", ".join([f'"{t}"' for t in search_terms])
    if not api_key or not text.strip():
        return "neutral"
    prompt = f"""From this story excerpt, what is the typical narrative role of the character "{character_name}" (referred to as: {terms_str})?
Choose ONE: hero, villain, mentor, sidekick, neutral.
- hero: protagonist who does good, defeats threats, protects others.
- villain: antagonist who causes fear/chaos, is opposed or defeated.
- mentor: guides or teaches another character.
- sidekick: supports the main character.
- neutral: no clear role or mixed.

Story excerpt:
"{text[:2000]}"

Reply with only one word: hero, villain, mentor, sidekick, or neutral."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 20
                }
            )
            if r.status_code != 200:
                return "neutral"
            content = (r.json().get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip().lower()
            for role in ("hero", "villain", "mentor", "sidekick", "neutral"):
                if role in content:
                    return role
            return "neutral"
    except Exception as e:
        print(f"⚠️ Character pattern analysis failed: {e}")
        return "neutral"


async def analyze_character_sentiment(
    text: str,
    character_name: str,
    character_aliases: list[str] = None,
    character_pattern: Optional[str] = None
) -> dict:
    """
    Analyze sentiment for a specific character in the text.
    
    Args:
        text: The full document text
        character_name: The name of the character to analyze
        character_aliases: Optional list of aliases for the character
        character_pattern: Optional narrative role (hero, villain, mentor, sidekick, neutral) for context
        
    Returns:
        Dictionary with:
        - mentions: List of dicts with sentence_index, sentence_text, sentiment, position
        - positive_percentage: Percentage of positive mentions (0-100)
        - neutral_percentage: Percentage of neutral mentions (0-100)
        - negative_percentage: Percentage of negative mentions (0-100)
        - trend_points: List of sentiment values over time for visualization
    """
    api_key = get_api_key()
    character_aliases = character_aliases or []
    
    # Build character search terms
    search_terms = [character_name.lower()] + [alias.lower() for alias in character_aliases]
    search_terms_str = ", ".join([f'"{term}"' for term in search_terms])
    pattern_hint = ""
    if character_pattern and character_pattern != "neutral":
        pattern_hint = f' This character was identified as typically "{character_pattern}". Use that: hero defeating threat = positive; hero accomplishments (spells, treasure, celebration, victory) = positive; villain causing fear/chaos or being defeated = negative. '
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using fallback sentiment analysis")
        return _fallback_character_sentiment(text, character_name, search_terms)
    
    prompt = f"""Analyze how the character "{character_name}" is portrayed in each sentence in narrative context. Stories often have heroes (do good, defeat threats) and villains (cause fear/chaos, are defeated).{pattern_hint} Judge accordingly. Is the character shown as likeable/admirable (positive), as mean/evil/cowardly (negative), or neither (neutral)? Use meaning and context—not just single words.


Important: If a character is merely part of the sentence (e.g. "the hero fought against the dragon") with no adjectives or other wording that portray that character positively or negatively, the sentence is neutral toward that character—use "neutral". Do not mark negative just because they are the opponent or mentioned in a fight.
Rules:
- "positive": The character is shown in a favorable light—brave, kind, competent, sympathetic, or as someone to root for. This includes: facing or overcoming danger (dark forests, raging rivers, fighting enemies); being praised, celebrated, honored, or rewarded (e.g. "celebrated the hero", "honored the hero", "became a legend"); doing good (defeating threats, protecting others); demonstrating power or competence (e.g. casting powerful spells, claiming treasure, receiving guidance from a wise figure, discovering something, achieving victory). When the character is the one succeeding, achieving, or being celebrated, mark positive—do NOT mark neutral.
- "neutral": Use when the character is neither clearly positive nor negative. This includes: purely factual or descriptive; or when the character is merely part of the sentence (e.g. "the hero fought against the dragon") with no adjectives or other wording that portray the character positively or negatively—the character is just mentioned, not framed. If the character is praised, celebrated, or shown succeeding, that is positive, not neutral.
- "negative": The character is shown in an unfavorable light—threatening, cruel, cowardly, mean, hostile, or as someone to fear/oppose. This applies when the character is the one being aggressive (fury, fierce, flames), retreating in shame, or defeated/slain (e.g. "the dragon retreated shamefully", "slay the fearsome dragon"). If the character is only the opponent in a fight (e.g. "the hero fought against the dragon") with no extra negative framing of that character, that is neutral, not negative.

Examples:
- "The hero traveled through dark forests and crossed raging rivers." → for hero: positive (hero is shown as brave/determined; dark/raging describe the environment, not the hero).
- "A fierce dragon guarded the treasure with flames and fury." → for dragon: negative (dragon is portrayed as threatening).
- "The dragon finally retreated into the shadows." → for dragon: negative (retreat = unfavorable).
- "The noble champion fought valiantly to slay the fearsome dragon." → for hero: positive (does good, defeats threat); for dragon: negative (causes fear, is slain).
- "The dragon's scales gleamed in the sun." → for dragon: neutral (descriptive only).
- "The kingdom celebrated the hero with a grand festival." → for hero: positive (character is celebrated/praised).
- "Magic filled the air as the hero cast powerful spells." → for hero: positive (hero demonstrates power/competence).
- "The hero fought bravely against the dragon in an epic battle." → for dragon: neutral (dragon is merely part of the sentence, no adjectives or framing); for hero: positive (hero defeats threat).

The character may be referred to as: {search_terms_str}

Text to analyze:
The input may be (A) one or more sentences in order, or (B) multiple segments separated by " --- SEGMENT --- " (each segment has 1-2 sentences before/after for context). For (B), output one sentiment per segment in order, using the segment context to judge how the character is portrayed.
"{text}"

Respond with ONLY a JSON array. One object per sentence that mentions the character, in the same order as in the text:
[
  {{"sentence_index": 0, "sentence_text": "...", "sentiment": "positive", "position": 0.0}},
  {{"sentence_index": 1, "sentence_text": "...", "sentiment": "negative", "position": 0.5}}
]
- sentence_index: 0-based index of that sentence in the text above.
- sentence_text: exact text of the sentence.
- sentiment: "positive", "neutral", or "negative" (your decision from context).
- position: 0.0 to 1.0 (where in the text).

Only include sentences that mention the character. No other text, no markdown, only the JSON array."""

    try:
        # Reduced timeout to 30 seconds for faster fallback to keyword-based analysis
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 2000
                }
            )
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Using fallback sentiment.")
                return _fallback_character_sentiment(text, character_name, search_terms)
            
            if response.status_code != 200:
                print(f"❌ Error analyzing character sentiment: {response.text}")
                return _fallback_character_sentiment(text, character_name, search_terms)
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print(f"🧠 Character Sentiment Analysis for {character_name}:", content[:200])
            
            # Clean up the response
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            content = content.strip()
            
            try:
                mentions = json.loads(content)
                if not isinstance(mentions, list):
                    mentions = []
                
                # Calculate percentages
                total = len(mentions)
                if total == 0:
                    return {
                        "mentions": [],
                        "positive_percentage": 0,
                        "neutral_percentage": 0,
                        "negative_percentage": 0,
                        "trend_points": []
                    }
                
                positive_count = sum(1 for m in mentions if m.get("sentiment") == "positive")
                neutral_count = sum(1 for m in mentions if m.get("sentiment") == "neutral")
                negative_count = sum(1 for m in mentions if m.get("sentiment") == "negative")
                
                # Generate trend points (simplified: map sentiment to numeric values)
                trend_points = []
                for mention in sorted(mentions, key=lambda x: x.get("position", 0)):
                    sentiment = mention.get("sentiment", "neutral")
                    if sentiment == "positive":
                        trend_points.append(0.7)  # High value for positive
                    elif sentiment == "negative":
                        trend_points.append(0.3)  # Low value for negative
                    else:
                        trend_points.append(0.5)  # Medium for neutral
                
                return {
                    "mentions": mentions,
                    "positive_percentage": int((positive_count / total) * 100),
                    "neutral_percentage": int((neutral_count / total) * 100),
                    "negative_percentage": int((negative_count / total) * 100),
                    "trend_points": trend_points
                }
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON: {e}")
                return _fallback_character_sentiment(text, character_name, search_terms)
                
    except Exception as e:
        print(f"Error analyzing character sentiment: {e}")
        return _fallback_character_sentiment(text, character_name, search_terms)


async def discover_characters_in_text(text: str) -> list[dict]:
    """
    Discover characters mentioned in the text using LLM.
    
    Args:
        text: The document text to analyze
        
    Returns:
        List of dicts with 'name' and optionally 'emoji' and 'aliases'
    """
    api_key = get_api_key()
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using fallback character discovery")
        return _fallback_character_discovery(text)
    
    prompt = f"""Analyze the following text and identify the main characters mentioned.
    
Text:
"{text}"

Identify the main characters (people, creatures, or entities that play significant roles in the story).
For each character, provide:
- name: The primary name or identifier
- aliases: Alternative names or ways the character is referred to (e.g., "the hero", "protagonist")
- role: Brief description of their role (e.g., "hero", "villain", "companion", "mentor")

Respond with ONLY a JSON array of character objects:
[
  {{
    "name": "Hero",
    "aliases": ["protagonist", "the hero", "main character"],
    "role": "hero"
  }},
  {{
    "name": "Dragon",
    "aliases": ["the dragon", "beast"],
    "role": "antagonist"
  }}
]

Only include characters that are actually mentioned in the text. If no characters are found, return an empty array [].
No explanations, no markdown, just the JSON array."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Using fallback character discovery.")
                return _fallback_character_discovery(text)
            
            if response.status_code != 200:
                print(f"❌ Error discovering characters: {response.text}")
                return _fallback_character_discovery(text)
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print(f"🧠 Character Discovery:", content[:200])
            
            # Clean up the response
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            content = content.strip()
            
            try:
                characters = json.loads(content)
                if not isinstance(characters, list):
                    characters = []
                return characters
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse character discovery JSON: {e}")
                return _fallback_character_discovery(text)
                
    except Exception as e:
        print(f"Error discovering characters: {e}")
        return _fallback_character_discovery(text)


def _fallback_character_discovery(text: str) -> list[dict]:
    """Simple fallback character discovery based on keywords."""
    characters = []
    text_lower = text.lower()
    
    # Common character roles
    role_keywords = {
        'hero': ['hero', 'heroine', 'protagonist', 'main character'],
        'villain': ['villain', 'antagonist', 'enemy', 'foe', 'evil'],
        'companion': ['companion', 'friend', 'ally', 'partner', 'sidekick'],
        'mentor': ['mentor', 'teacher', 'guide', 'wizard', 'wise'],
        'dragon': ['dragon', 'beast', 'monster', 'creature']
    }
    
    for role, keywords in role_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                characters.append({
                    "name": role.capitalize(),
                    "aliases": keywords,
                    "role": role
                })
                break
    
    # Also look for capitalized words (potential character names)
    words = text.split()
    seen_names = set()
    for i, word in enumerate(words):
        if i > 0:  # Skip first word of sentences
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                name_lower = clean_word.lower()
                if name_lower not in seen_names and name_lower not in ['the', 'this', 'that', 'there']:
                    seen_names.add(name_lower)
                    characters.append({
                        "name": clean_word,
                        "aliases": [name_lower],
                        "role": "character"
                    })
    
    # Remove duplicates
    unique_characters = []
    seen = set()
    for char in characters:
        name_key = char["name"].lower()
        if name_key not in seen:
            seen.add(name_key)
            unique_characters.append(char)
    
    return unique_characters[:10]  # Limit to 10 characters


def _fallback_character_sentiment(text: str, character_name: str, search_terms: list) -> dict:
    """Simple fallback sentiment analysis based on keyword matching."""
    import re
    
    # Split text into sentences
    sentences = re.split(r'[.!?]+\s+', text)
    mentions = []
    
    character_lower = character_name.lower()
    search_terms_lower = [term.lower() for term in search_terms]
    
    for idx, sentence in enumerate(sentences):
        sentence_lower = sentence.lower()
        
        # Check if character is mentioned
        is_mentioned = False
        for term in search_terms_lower:
            if re.search(r'\b' + re.escape(term) + r'\b', sentence_lower):
                is_mentioned = True
                break
        
        if is_mentioned:
            # Character portrayal: words that depict the character unfavorably vs favorably
            positive_words = [
                'brave', 'hero', 'good', 'kind', 'wise', 'strong', 'victory', 'save', 'help', 'noble', 'protect',
                'celebrated', 'celebrate', 'honored', 'honor', 'legend', 'praised', 'praise',
                'powerful', 'spell', 'spells', 'treasure', 'discovered', 'guidance', 'achieved', 'achievement',
                'wisdom', 'appeared', 'offered'
            ]
            # Words that portray the character unfavorably (not environment: "dark forests", "raging rivers" are setting, not character)
            negative_words = [
                'evil', 'fear', 'danger', 'attack', 'destroy', 'hate', 'angry',
                'cowardly', 'coward', 'gloomy', 'slunk', 'slink', 'fled', 'retreat', 'weak',
                'cruel', 'villain', 'monster', 'beast', 'ruthless', 'foolish', 'betray',
                'fury', 'furious', 'fierce', 'flames', 'menace', 'menacing', 'fearsome', 'slay', 'slain'
            ]
            
            sentence_lower = sentence.lower()
            positive_score = sum(1 for word in positive_words if word in sentence_lower)
            negative_score = sum(1 for word in negative_words if word in sentence_lower)
            
            if positive_score > negative_score:
                sentiment = "positive"
            elif negative_score > positive_score:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            position = idx / max(1, len(sentences))
            mentions.append({
                "sentence_index": idx,
                "sentence_text": sentence.strip(),
                "sentiment": sentiment,
                "position": position
            })
    
    total = len(mentions)
    if total == 0:
        return {
            "mentions": [],
            "positive_percentage": 0,
            "neutral_percentage": 0,
            "negative_percentage": 0,
            "trend_points": []
        }
    
    positive_count = sum(1 for m in mentions if m["sentiment"] == "positive")
    neutral_count = sum(1 for m in mentions if m["sentiment"] == "neutral")
    negative_count = sum(1 for m in mentions if m["sentiment"] == "negative")
    
    trend_points = []
    for mention in sorted(mentions, key=lambda x: x["position"]):
        if mention["sentiment"] == "positive":
            trend_points.append(0.7)
        elif mention["sentiment"] == "negative":
            trend_points.append(0.3)
        else:
            trend_points.append(0.5)
    
    return {
        "mentions": mentions,
        "positive_percentage": int((positive_count / total) * 100),
        "neutral_percentage": int((neutral_count / total) * 100),
        "negative_percentage": int((negative_count / total) * 100),
        "trend_points": trend_points
    }


async def generate_chapter_emoji(chapter_content: str) -> str:
    """
    Generate a single emoji suggestion for a chapter based on its content.
    
    Args:
        chapter_content: The full text content of the chapter
        
    Returns:
        Suggested emoji string (single emoji)
    """
    api_key = get_api_key()
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using fallback emoji")
        return _fallback_emoji_suggestion(chapter_content)
    
    prompt = f"""You are helping a fiction writer choose an emoji for a chapter.

Read the following chapter content and suggest ONE single emoji that best captures the essence, main theme, or key element of this chapter.

Chapter content:
"{chapter_content}"

Rules:
- Return ONLY a single emoji character
- Choose an emoji that represents the main theme, key character, important object, or central emotion
- Make it evocative and memorable
- No explanations, no text, just the emoji

Example outputs:
- 🐉 (for a dragon chapter)
- ⚔️ (for a battle chapter)
- 👑 (for a royal chapter)
- ✨ (for a magic chapter)
- 🏰 (for a castle chapter)
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-Title": "Story Writing Assistant"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.8,
                    "max_tokens": 10
                }
            )
            
            if response.status_code == 429:
                print("⚠️ OpenRouter free tier limit reached (429). Using fallback emoji.")
                return _fallback_emoji_suggestion(chapter_content)
            
            if response.status_code != 200:
                print(f"❌ Error generating emoji: {response.text}")
                return _fallback_emoji_suggestion(chapter_content)
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Extract emoji from response - take first emoji found
            import re
            emoji_pattern = re.compile(
                r'[\U0001F300-\U0001F9FF]|'  # Miscellaneous Symbols and Pictographs
                r'[\U00002600-\U000027BF]|'  # Miscellaneous Symbols
                r'[\U0001F600-\U0001F64F]|'  # Emoticons
                r'[\U0001F680-\U0001F6FF]|'  # Transport and Map Symbols
                r'[\U0001F1E0-\U0001F1FF]|'  # Flags
                r'[\U00002702-\U000027B0]|'  # Dingbats
                r'[\U000024C2-\U0001F251]'    # Enclosed characters
            )
            emojis = emoji_pattern.findall(content)
            
            if emojis:
                return emojis[0]
            
            return _fallback_emoji_suggestion(chapter_content)
            
    except Exception as e:
        print(f"Error generating chapter emoji: {e}")
        return _fallback_emoji_suggestion(chapter_content)


def _fallback_emoji_suggestion(content: str) -> str:
    """Simple fallback emoji suggestion based on keywords."""
    if not content or len(content.strip()) < 10:
        return "📖"
    
    content_lower = content.lower()
    
    # Use keyword-based emoji selection
    if any(word in content_lower for word in ['dragon', 'monster', 'beast']):
        return "🐉"
    if any(word in content_lower for word in ['king', 'queen', 'prince', 'princess', 'royal', 'crown']):
        return "👑"
    if any(word in content_lower for word in ['magic', 'spell', 'wizard', 'witch', 'enchant']):
        return "✨"
    if any(word in content_lower for word in ['fight', 'battle', 'sword', 'warrior', 'combat']):
        return "⚔️"
    if any(word in content_lower for word in ['castle', 'fortress', 'palace']):
        return "🏰"
    if any(word in content_lower for word in ['love', 'heart', 'romance']):
        return "❤️"
    if any(word in content_lower for word in ['treasure', 'gold', 'coin', 'jewel']):
        return "💎"
    if any(word in content_lower for word in ['forest', 'tree', 'wood']):
        return "🌲"
    if any(word in content_lower for word in ['ocean', 'sea', 'water', 'wave']):
        return "🌊"
    if any(word in content_lower for word in ['moon', 'night', 'dark']):
        return "🌙"
    if any(word in content_lower for word in ['sun', 'day', 'light']):
        return "☀️"
    
    # Default fallback
    return "📖"