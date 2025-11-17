"""AI client for together.ai integration."""
import os
from typing import Optional
import httpx

# TODO: Replace with actual together.ai API endpoint when ready
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")


async def generate_emojis_for_sentence(text: str) -> list[str]:
    """
    Generate up to 5 emojis that capture the mood/plot of the given text.
    
    Args:
        text: The sentence text to analyze
        
    Returns:
        List of 1-5 emoji strings
        
    TODO: Implement actual together.ai API call with proper prompt engineering.
    For now, returns dummy emojis for testing.
    """
    # TEMPORARY: Return dummy emojis for MVP
    # This allows frontend-backend integration testing before AI is fully wired
    dummy_emojis = ["😱", "✨", "🧙‍♂️", "📖", "🌙"]
    
    # TODO: Uncomment and implement when ready
    # if not TOGETHER_API_KEY:
    #     raise ValueError("TOGETHER_API_KEY environment variable not set")
    #
    # prompt = f"""Analyze the following sentence and suggest up to 5 emojis that capture its mood, emotion, and plot significance:
    #
    # Sentence: {text}
    #
    # Return only the emojis, separated by spaces, no other text."""
    #
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         TOGETHER_API_URL,
    #         headers={
    #             "Authorization": f"Bearer {TOGETHER_API_KEY}",
    #             "Content-Type": "application/json"
    #         },
    #         json={
    #             "model": "meta-llama/Llama-3-70b-chat-hf",  # Example model
    #             "messages": [
    #                 {"role": "system", "content": "You are a creative writing assistant that suggests emojis to represent story emotions and plot."},
    #                 {"role": "user", "content": prompt}
    #             ],
    #             "max_tokens": 50,
    #             "temperature": 0.7
    #         }
    #     )
    #     response.raise_for_status()
    #     result = response.json()
    #     
    #     # Parse emojis from response
    #     emojis_text = result["choices"][0]["message"]["content"].strip()
    #     emojis = emojis_text.split()[:5]  # Max 5 emojis
    #     return emojis
    
    return dummy_emojis[:3]  # Return 3 dummy emojis for now


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
        
    TODO: Implement actual together.ai API call with proper prompt engineering.
    For now, returns dummy text for testing.
    """
    # TEMPORARY: Return dummy text for MVP
    dummy_text = f"A mysterious figure emerged from the shadows, carrying ancient secrets. {' '.join(emojis)}"
    
    # TODO: Uncomment and implement when ready
    # if not TOGETHER_API_KEY:
    #     raise ValueError("TOGETHER_API_KEY environment variable not set")
    #
    # emoji_str = " ".join(emojis)
    # context_part = f"\n\nContext from the story:\n{context}" if context else ""
    #
    # prompt = f"""Generate 1-2 sentences for a creative story that match these emojis: {emoji_str}
    #
    # The emojis represent the mood, emotion, and plot direction.{context_part}
    #
    # Write naturally as part of a story:"""
    #
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         TOGETHER_API_URL,
    #         headers={
    #             "Authorization": f"Bearer {TOGETHER_API_KEY}",
    #             "Content-Type": "application/json"
    #         },
    #         json={
    #             "model": "meta-llama/Llama-3-70b-chat-hf",
    #             "messages": [
    #                 {"role": "system", "content": "You are a creative writing assistant helping authors generate story text."},
    #                 {"role": "user", "content": prompt}
    #             ],
    #             "max_tokens": 100,
    #             "temperature": 0.8
    #         }
    #     )
    #     response.raise_for_status()
    #     result = response.json()
    #     
    #     generated_text = result["choices"][0]["message"]["content"].strip()
    #     return generated_text
    
    return dummy_text


def check_api_key_configured() -> bool:
    """Check if the together.ai API key is configured."""
    return bool(TOGETHER_API_KEY)
