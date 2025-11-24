"""AI client for OpenRouter integration."""
import os
from typing import Optional
import httpx
import json

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_api_key() -> str:
    """Get API key dynamically to support hot reload."""
    return os.getenv("OPENROUTER_API_KEY", "")

# Use Mistral's free model - stable and reliable
MODEL_NAME = "mistralai/mistral-small-3.2-24b-instruct:free"


async def generate_emojis_for_sentence(text: str) -> list[str]:
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

