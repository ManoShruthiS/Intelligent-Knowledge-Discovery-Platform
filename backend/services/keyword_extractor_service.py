import re
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

DEFAULT_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on", "at", "for", "with",
    "as", "by", "from", "it", "its", "he", "she", "they", "we", "you",
    "i", "me", "him", "her", "us", "them", "my", "your", "his", "our",
    "their", "this", "that", "these", "those", "can", "will", "would",
    "should", "has", "have", "had", "do", "does", "did", "not", "no",
    "also", "using", "paper", "method", "results", "model", "data", "figure"
}

class KeywordExtractorService:
    """
    Extracts high-value technical keywords and topic tags from document text.
    """
    @classmethod
    def extract_keywords(cls, text: str, max_keywords: int = 10, min_len: int = 4) -> List[str]:
        if not text or not isinstance(text, str):
            return []
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered = [w for w in words if len(w) >= min_len and w not in DEFAULT_STOPWORDS]
        
        counts = {}
        for w in filtered:
            counts[w] = counts.get(w, 0) + 1
            
        sorted_keywords = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in sorted_keywords[:max_keywords]]

keyword_extractor_service = KeywordExtractorService()
