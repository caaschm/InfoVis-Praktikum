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
MODEL_NAME = "mistralai/devstral-small-2505"


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
            "microsoft/phi-4:free"
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
    
async def generate_story_arc(text: str, granularity: int = 10) -> dict:
    """
    Analyze the narrative arc and return a JSON dict:
    {
      "arc": [0.0..1.0],         # length == granularity
      "beats": [{"name": "...", "position": 0.0..1.0, "note": "..."}]
    }
    """
    api_key = get_api_key()

    # Simple fallback: neutral arc with optional center peak if "climax" words found
    if not api_key:
        words = text.lower()
        arc = [0.3] * granularity
        if any(w in words for w in ["climax", "climactic", "finale", "showdown", "battle", "fight"]):
            arc[granularity // 2] = 0.95
        return {"arc": arc, "beats": []}

    prompt = f"""
    Analyze the following text and compute a story arc as an array of {granularity} numeric values between 0 and 1,
    where 0 means no dramatic tension and 1 means peak dramatic tension.

    Also identify up to 5 key beats (e.g., inciting incident, midpoint, climax) with a short name and normalized position (0.0-1.0).

    Return the result EXACTLY as a JSON object like:
    {{ "arc": [ ... ], "beats": [{{"name":"", "position":0.0, "note":""}}, ...] }}
    Do not add extra commentary or markdown.

    Text:
    {text}
    """

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
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
                    "temperature": 0.6,
                    "max_tokens": 300,
                },
            )

        if res.status_code != 200:
            print(f"❌ Error response: {res.text}")
            return {"arc": [0.5] * granularity, "beats": []}

        result = res.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        # Remove code fences and try to extract the first JSON object
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            m = re.search(r'({[\s\S]*})', content)
            if m:
                parsed = json.loads(m.group(1))
            else:
                raise

        arc_raw = parsed.get("arc", [])
        beats = parsed.get("beats", [])

        # Normalize/convert arc values to floats in range 0..1
        arc_vals = []
        for v in arc_raw:
            try:
                fv = float(v)
            except Exception:
                fv = 0.5
            # If values look like 0..100, scale down
            if fv > 1.1:
                fv = max(0.0, min(1.0, fv / 100.0))
            else:
                fv = max(0.0, min(1.0, fv))
            arc_vals.append(fv)

        # If length mismatch, simple linear resample/interpolate
        if len(arc_vals) != granularity and len(arc_vals) > 0:
            src_len = len(arc_vals)
            new = []
            for i in range(granularity):
                pos = i * (src_len - 1) / (granularity - 1) if granularity > 1 else 0
                lo = int(pos)
                hi = min(lo + 1, src_len - 1)
                t = pos - lo
                new.append((1 - t) * arc_vals[lo] + t * arc_vals[hi])
            arc_vals = new

        # Ensure to always return exactly `granularity` floats
        if len(arc_vals) != granularity:
            arc_vals = [0.5] * granularity

        return {"arc": arc_vals, "beats": beats}
    except Exception as e:
        print(f"❌ Error generating story arc: {e}")
        return {"arc": [0.5] * granularity, "beats": []}