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
MODEL_NAME = "xiaomi/mimo-v2-flash:free"


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
    Simple fallback when AI is unavailable - returns neutral values.
    
    Args:
        text: The text to analyze
        
    Returns:
        Dictionary with neutral drama, humor, conflict, mystery values (0-100)
    """
    # Return neutral values as fallback
    return {
        "drama": 50,
        "humor": 50,
        "conflict": 50,
        "mystery": 50
    }

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


Respond ONLY in JSON:
{{
  "summary": "...",
  "ideas": ["...", "...", "..."],
  "preview": "..."
}}
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
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6,
                    "max_tokens": 300,
                },
            )

        if res.status_code != 200:
            print(f"❌ Error response: {res.text}")
            raise Exception(f"API returned status {res.status_code}")

        raw = res.json()["choices"][0]["message"]["content"].strip()

        # Remove markdown fences if present
        cleaned = re.sub(r"```json|```", "", raw).strip()

        return json.loads(cleaned)

    except Exception as e:
        print(f"❌ Error generating spider intent: {type(e).__name__}: {e}")
        print("INTENT ERROR RAW:", raw if "raw" in locals() else "NO RAW")
        return {
            "summary": "The AI could not generate a specific suggestion.",
            "ideas": ["Try adjusting emotional tone.", "Modify character choices.", "Change pacing or tension."],
            "preview": ""
        }
