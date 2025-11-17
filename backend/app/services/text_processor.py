"""Text processing utilities for sentence splitting."""
import re
from typing import List


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using basic heuristics.
    
    Args:
        text: The full text to split
        
    Returns:
        List of sentence strings
        
    TODO: Consider using a more sophisticated sentence tokenizer
    like NLTK or spaCy if needed for better accuracy.
    """
    # Basic sentence splitting on .!? followed by space/newline
    # This is a simple implementation; can be enhanced later
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Filter out empty strings and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences
