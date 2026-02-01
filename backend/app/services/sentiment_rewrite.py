"""Rewrite sentence for target sentiment (Character Sentiment manual edit)."""
from __future__ import annotations

import re
import json
import httpx
from app.services.ai_client import get_api_key, MODEL_NAME, OPENROUTER_API_URL


def _extract_json_from_response(content: str) -> dict | None:
    """Extract a JSON object from LLM response (may contain markdown or extra text)."""
    if not content or not content.strip():
        return None
    # Strip markdown code blocks
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"```\s*$", "", content)
    content = content.strip()
    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Find first { and then match braces to get full JSON object
    start = content.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    quote_char = None
    for i, c in enumerate(content[start:], start=start):
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start : i + 1])
                    except json.JSONDecodeError:
                        return None
            elif c in ('"', "'"):
                in_string = True
                quote_char = c
        elif c == quote_char:
            in_string = False
    return None


async def rewrite_sentence_for_sentiment(
    sentence_text: str,
    target_sentiment: str,
    character_name: str | None = None,
) -> dict:
    """
    Rewrite a sentence to match a target emotional tone (positive, neutral, or negative).
    If character_name is given, focus the rewrite on how that character is portrayed.
    Returns dict with rewritten_text and optional explanation.
    """
    api_key = get_api_key()
    if not api_key:
        return {
            "rewritten_text": sentence_text,
            "explanation": "OpenRouter API key not set. Add OPENROUTER_API_KEY to backend/.env (see .env.example)."
        }
    # How the character (subject) is depicted—favorable, neutral, or unfavorable
    portrayal_guide = {
        "positive": "depict the character in a favorable light (heroic, sympathetic, admirable, kind)",
        "neutral": "depict the character in a neutral, factual way (neither clearly favorable nor unfavorable)",
        "negative": "depict the character in an unfavorable light (villainous, cruel, foolish, or unsympathetic)",
    }
    guide = portrayal_guide.get(target_sentiment.lower(), portrayal_guide["neutral"])
    subject = f' the character "{character_name}"' if (character_name and character_name.strip()) else " the character/subject"
    prompt = f"""Rewrite the following sentence so{subject} is {guide}. Change only the wording that affects how the character is portrayed—keep the same events and length. Do not change the general mood of the scene; focus on how the character is depicted.

Original sentence:
"{sentence_text}"

Respond with ONLY a JSON object:
{{"rewritten_text": "your rewritten sentence here", "explanation": "optional brief reason"}}"""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
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
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 400
                }
            )
            if response.status_code != 200:
                try:
                    err_body = response.json()
                    msg = err_body.get("error", {}).get("message", err_body.get("message", response.text[:200]))
                except Exception:
                    msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                print(f"Sentiment rewrite API error: {response.status_code} — {msg}")
                if response.status_code == 401:
                    explanation = "Invalid or missing API key. Check OPENROUTER_API_KEY in backend/.env."
                elif response.status_code == 429:
                    explanation = "Rate limit reached. Please try again in a moment."
                else:
                    explanation = f"API error ({response.status_code}). Try again or check backend logs."
                return {"rewritten_text": sentence_text, "explanation": explanation}
            try:
                body = response.json()
            except Exception as e:
                print(f"Sentiment rewrite: invalid JSON response: {e}")
                return {"rewritten_text": sentence_text, "explanation": "Invalid API response. Try again."}
            choices = body.get("choices") or []
            if not choices:
                return {"rewritten_text": sentence_text, "explanation": "API returned no suggestion. Try again."}
            content = (choices[0].get("message") or {}).get("content") or ""
            content = (content or "").strip()
            data = _extract_json_from_response(content)
            if not data:
                print(f"Sentiment rewrite: could not parse JSON from: {content[:300]}")
                return {"rewritten_text": sentence_text, "explanation": "Could not parse AI response. Try again."}
            rewritten = data.get("rewritten_text") or sentence_text
            if not isinstance(rewritten, str):
                rewritten = sentence_text
            return {
                "rewritten_text": rewritten.strip(),
                "explanation": data.get("explanation") if isinstance(data.get("explanation"), str) else None
            }
    except httpx.TimeoutException:
        print("Sentiment rewrite: request timeout")
        return {"rewritten_text": sentence_text, "explanation": "Request timed out. Try again."}
    except Exception as e:
        print(f"Error rewriting sentence for sentiment: {e}")
        return {"rewritten_text": sentence_text, "explanation": f"Error: {str(e)[:100]}"}
