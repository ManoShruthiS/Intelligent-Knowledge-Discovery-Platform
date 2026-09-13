import re
import json
from typing import List, Dict
MAX_CHUNK_CHARS = 4000
OVERLAP_CHARS = 800

class DocumentChunker:

    def __init__(self, max_chars=MAX_CHUNK_CHARS, overlap=OVERLAP_CHARS):
        self.max_chars = max(256, int(max_chars))
        self.overlap = max(0, min(int(overlap), self.max_chars - 1))

    def chunk_document(self, document_data: dict) -> List[Dict]:
        pages = document_data.get('pages', [])
        all_chunks: List[Dict] = []
        current_chunk_index = 0
        for page in pages:
            page_text = page.get('text', '')
            page_number = page.get('page_number')
            spans = sorted(page.get('spans') or [], key=lambda s: s.get('char_start', 0))
            page_width = page.get('width')
            page_height = page.get('height')
            if not page_text.strip():
                continue
            page_splits = self._recursive_split(page_text, self.max_chars)
            last_chunk_end = 0
            for split_text in page_splits:
                chunk_text = split_text.strip()
                if not chunk_text:
                    continue
                char_start, char_end = self._locate_in_page(page_text, chunk_text, last_chunk_end)
                last_chunk_end = char_end
                bboxes = self._bboxes_for_range(spans, char_start, char_end)
                all_chunks.append({'chunk_index': current_chunk_index, 'text': chunk_text, 'page_number': page_number, 'char_start': char_start, 'char_end': char_end, 'bboxes_json': json.dumps(bboxes) if bboxes else None, 'page_width': page_width, 'page_height': page_height})
                current_chunk_index += 1
        return all_chunks

    @staticmethod
    def _locate_in_page(page_text: str, chunk_text: str, search_start: int):
        idx = page_text.find(chunk_text, search_start)
        if idx == -1:
            idx = page_text.find(chunk_text)
        if idx == -1:
            return (search_start, search_start + len(chunk_text))
        return (idx, idx + len(chunk_text))

    @staticmethod
    def _bboxes_for_range(spans: List[Dict], char_start: int, char_end: int) -> List[List[float]]:
        if not spans:
            return []
        out: List[List[float]] = []
        for s in spans:
            s_start = s['char_start']
            s_end = s['char_end']
            if s_end <= char_start:
                continue
            if s_start >= char_end:
                break
            out.append(s['bbox'])
        return out

    def _recursive_split(self, text: str, max_length: int, sep_idx: int=0) -> List[str]:
        if len(text) <= max_length:
            return [text]
        separators = ['\n\n', '\n', '. ', '? ', '! ', ' ']
        for i in range(sep_idx, len(separators)):
            separator = separators[i]
            if separator in text:
                splits = text.split(separator)
                splits = [s + separator if i < len(splits) - 1 else s for i, s in enumerate(splits)]
                if any((len(s) > 0 and len(s) < len(text) for s in splits)):
                    out: List[str] = []
                    for s in splits:
                        if len(s) > max_length:
                            out.extend(self._recursive_split(s, max_length, i + 1))
                        else:
                            out.append(s)
                    return self._merge_splits(out, max_length)
        return self._force_split(text, max_length)

    def _merge_splits(self, splits: List[str], max_length: int) -> List[str]:
        expanded: List[str] = []
        for s in splits:
            if len(s) > max_length:
                expanded.extend(self._force_split(s, max_length))
            else:
                expanded.append(s)
        splits = expanded
        chunks = []
        current_chunk = ''
        for split in splits:
            if len(current_chunk) + len(split) > max_length and current_chunk:
                chunks.append(current_chunk)
                if self.overlap > 0 and len(current_chunk) > self.overlap:
                    overlap_text = current_chunk[-self.overlap:]
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
        chunks = []
        start = 0
        eff_overlap = min(self.overlap, max_length - 1)
        step = max(1, max_length - eff_overlap)
        while start < len(text):
            end = min(start + max_length, len(text))
            chunks.append(text[start:end])
            start += step
            if start >= len(text):
                break
        return chunks
