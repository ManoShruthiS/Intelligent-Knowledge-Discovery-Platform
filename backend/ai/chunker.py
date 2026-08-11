import re
from typing import List, Dict

# Character-based approximation for chunks
# 1 token ≈ 4 characters
# Target: ~800-1200 tokens -> ~3200-4800 characters
MAX_CHUNK_CHARS = 4000
OVERLAP_CHARS = 800

class DocumentChunker:
    """
    Splits document pages into meaningful chunks, attempting to respect
    natural boundaries (paragraphs, sentences, words) while preserving
    page number references.
    """

    def __init__(self, max_chars=MAX_CHUNK_CHARS, overlap=OVERLAP_CHARS):
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk_document(self, document_data: dict) -> List[Dict]:
        """
        Takes the output of document_processor and returns a list of chunk dictionaries.
        """
        pages = document_data.get("pages", [])
        
        all_chunks = []
        current_chunk_index = 0
        
        for page in pages:
            page_text = page.get("text", "")
            page_number = page.get("page_number")
            
            if not page_text.strip():
                continue
                
            # Perform recursive splitting on this page's text
            page_splits = self._recursive_split(page_text, self.max_chars)
            
            # Since we split by page, we can just assign the page number to all chunks from this page.
            # If a chunk overlaps across pages, this simple strategy doesn't carry overlap *across* page boundaries,
            # which is acceptable for maintaining accurate page mapping without heavy complexity.
            
            for split_text in page_splits:
                all_chunks.append({
                    "chunk_index": current_chunk_index,
                    "text": split_text.strip(),
                    "page_number": page_number
                })
                current_chunk_index += 1
                
        return all_chunks

    def _recursive_split(self, text: str, max_length: int) -> List[str]:
        """
        Recursively splits text using natural boundaries.
        Returns a list of chunks. Overlap is applied here.
        """
        if len(text) <= max_length:
            return [text]
            
        # Define boundary separators in order of preference
        separators = ["\n\n", "\n", ". ", "? ", "! ", " "]
        
        for separator in separators:
            # Check if this separator exists and can split the text
            if separator in text:
                splits = text.split(separator)
                # Re-add the separator to the splits (except for the last one)
                splits = [s + separator if i < len(splits) - 1 else s for i, s in enumerate(splits)]
                
                # Check if this split actually reduces size
                if any(len(s) > 0 and len(s) < len(text) for s in splits):
                    return self._merge_splits(splits, max_length)
                    
        # If no separator worked (e.g., extremely long word/string), force split by characters
        return self._force_split(text, max_length)

    def _merge_splits(self, splits: List[str], max_length: int) -> List[str]:
        """
        Merges small splits into chunks up to max_length, adding overlap.
        """
        chunks = []
        current_chunk = ""
        
        for split in splits:
            if len(current_chunk) + len(split) > max_length and current_chunk:
                chunks.append(current_chunk)
                
                # Start new chunk with overlap from the end of current_chunk
                if self.overlap > 0 and len(current_chunk) > self.overlap:
                    # Try to find a clean overlap boundary (e.g., start of a sentence or word)
                    overlap_text = current_chunk[-self.overlap:]
                    # Simple heuristic: snap to the first space in the overlap text to avoid partial words
                    space_idx = overlap_text.find(' ')
                    if space_idx != -1 and space_idx < len(overlap_text) - 1:
                        overlap_text = overlap_text[space_idx + 1:]
                    current_chunk = overlap_text + split
                else:
                    current_chunk = split
            else:
                current_chunk += split
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _force_split(self, text: str, max_length: int) -> List[str]:
        """
        Fallback: strictly splits by characters if no natural boundaries exist.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_length, len(text))
            chunks.append(text[start:end])
            start += max_length - self.overlap
            if start >= len(text):
                break
        return chunks
