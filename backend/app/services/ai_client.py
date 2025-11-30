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


async def generate_emojis_for_sentence(text: str) -> list[str]:
    """
    Generate up to 5 emojis that capture the mood/plot of the given text.
    
    Args:
        text: The sentence text to analyze
        
    Returns:
        List of 1-5 emoji strings
    """
    api_key = get_api_key()
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found - using keyword-based fallback")
        return _keyword_based_emoji_selection(text)
    
    print(f"🔑 Using API key: {api_key[:15]}...{api_key[-4:]}")
    
    # 🎭 Extract characters/nouns for consistency
    characters = _extract_character_names(text)
    
    # 🎭 Build character mapping context
    character_context = ""
    if characters:
        mapped_chars = []
        for char in characters:
            if char in _character_emoji_cache:
                mapped_chars.append(f"{char} → {_character_emoji_cache[char]}")
        if mapped_chars:
            character_context = f"\n\nIMPORTANT - Use these consistent character emojis:\n" + "\n".join(mapped_chars)
    
    prompt = f"""Analyze this sentence and suggest 3-5 emojis that capture its meaning.

🎯 PRIORITY: Characters and nouns (people, creatures, objects) are MOST important!
Always include emojis for any characters/creatures mentioned.

Sentence: "{text}"
{character_context}

Respond with ONLY emojis separated by spaces. No text, no explanations.
Example: 🦸 ⚔️ 🐉 (hero fighting dragon)"""

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
                return _keyword_based_emoji_selection(text)
            
            result = response.json()
            
            # Extract emojis from response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ AI response: {content}")
            
            # Extract emojis (characters with unicode > 127)
            emojis = [char for char in content if char.strip() and ord(char) > 127]
            
            if emojis:
                # 🎭 Update character-emoji cache for consistency
                _update_character_emoji_mapping(text, emojis)
                return emojis[:5]
            else:
                print("⚠️  No emojis found in response, using keyword fallback")
                return _keyword_based_emoji_selection(text)
            
    except Exception as e:
        print(f"❌ Error calling OpenRouter: {type(e).__name__}: {e}")
        return _keyword_based_emoji_selection(text)


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
    people_creature_emojis = [e for e in emojis if ord(e) in range(0x1F600, 0x1F650) or 
                              ord(e) in range(0x1F400, 0x1F4D0) or
                              e in ['👑', '⚔️', '🏰', '🦸', '🦹', '👼', '😈', '👻', '🧙', '🧚', '🧛', '🧜']]
    
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

