from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
ANAPHORIC_TRIGGERS: List[Tuple[str, str]] = [('\\bthe\\s+(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\\s+(?:one|approach|method|paper|model|architecture|technique|framework|dataset|result)?\\b', 'ordinal'), ('\\bthe\\s+first\\s+(?:one|approach|method|paper|model|architecture)\\b', 'first'), ('\\bthe\\s+second\\s+(?:one|approach|method|paper|model|architecture)\\b', 'second'), ('\\bthe\\s+third\\s+(?:one|approach|method|paper|model|architecture)\\b', 'third'), ('\\bthe\\s+last\\s+(?:one|approach|method|paper|model|architecture)\\b', 'last'), ('\\bit\\b', 'it'), ('\\bthey\\b', 'they'), ('\\bthem\\b', 'them'), ('\\btheir\\b', 'their'), ('\\bthose\\b', 'those'), ('\\bthis\\s+(?:approach|method|paper|model|architecture|technique|framework)\\b', 'this_named'), ('\\bthat\\s+(?:approach|method|paper|model|architecture|technique|framework)\\b', 'that_named')]
KNOWN_ACRONYMS = {'ai', 'ml', 'nlp', 'llm', 'rag', 'pdf', 'url', 'api', 'bert', 'gpt', 'llama', 't5', 'vae', 'gan', 'cnn', 'rnn', 'lstm', 'gru', 'knn', 'svm', 'rlhf', 'dpo', 'sft', 'qa', 'tts', 'asr', 'bleu', 'rouge', 'meteor', 'nli'}

@dataclass
class ResolverResult:
    rewritten_question: str
    resolved_topics: List[str]
    confident_topics: List[str]
    ambiguous_resolutions: List[str]

    def summary(self) -> str:
        bits = []
        if self.confident_topics:
            bits.append('resolved=' + ','.join(self.confident_topics))
        if self.ambiguous_resolutions:
            bits.append('ambiguous=' + ','.join(self.ambiguous_resolutions))
        return '; '.join(bits)

def _history_entities(messages: Sequence[Dict]) -> List[Tuple[str, str, int]]:
    SENTENCE_LEADING_VERBS = {'tell', 'show', 'list', 'find', 'get', 'fetch', 'describe', 'explain', 'compare', 'define', 'summarize', 'give', 'use', 'provide', 'identify', 'name', 'say', 'elaborate'}
    raw: List[Tuple[str, str, int]] = []
    n = len(messages)
    for i, m in enumerate(messages):
        content = m.get('content') or '' if isinstance(m, dict) else ''
        if not content:
            continue
        for hit in re.finditer('(?<![\\w])([A-Z][A-Za-z0-9]+(?:[-–][A-Z][A-Za-z0-9]+)*(?:\\s+[A-Z][a-zA-Z]+)*)', content):
            ent = hit.group(1).strip().replace('–', '-')
            low = ent.lower()
            if len(ent) >= 3 and low not in _STOPWORDS and (low not in SENTENCE_LEADING_VERBS):
                raw.append((ent, 'phrase', i))
        for hit in re.finditer('\\b([A-Z]{2,}|[A-Z]\\d[A-Z0-9]*)\\b', content):
            raw.append((hit.group(1), 'acronym', i))
        for hit in re.findall('\\b([a-z]{2,5})\\b', content.lower()):
            if hit in KNOWN_ACRONYMS:
                raw.append((hit.upper(), 'acronym', i))
        for hit in re.finditer('\\b(19|20)\\d{2}\\b', content):
            raw.append((hit.group(0), 'year', i))
        for hit in re.finditer('(?<![\\w])([A-Z][a-zA-Z]{2,})\\b', content):
            word = hit.group(1)
            low = word.lower()
            if low not in _STOPWORDS and low not in SENTENCE_LEADING_VERBS:
                raw.append((word, 'noun', i))
    by_stem: Dict[str, Tuple[str, str, int]] = {}
    for ent, kind, idx in raw:
        stem = ent.split('-')[0].split()[0].lower()
        if stem not in by_stem or len(ent) > len(by_stem[stem][0]) or (len(ent) == len(by_stem[stem][0]) and idx > by_stem[stem][2]):
            by_stem[stem] = (ent, kind, idx)
    out = list(by_stem.values())
    out.sort(key=lambda t: -t[2])
    return out
_STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'these', 'those', 'it', 'its', 'i', 'you', 'he', 'she', 'we', 'they', 'them', 'my', 'your', 'our', 'their', 'his', 'her', 'what', 'how', 'why', 'when', 'where', 'who', 'which', 'do', 'does', 'did', 'would', 'could', 'should', 'shall', 'may', 'might', 'must', 'can', 'tell', 'explain', 'describe', 'show', 'give', 'list', 'find', 'between', 'compare', 'use', 'used', 'using', 'having', 'have', 'has', 'had', 'make', 'makes', 'made', 'got', 'get', 'getting', 'need', 'needs', 'needed', 'more', 'most', 'much', 'many', 'very', 'such', 'some', 'any', 'all', 'each', 'every', 'first', 'second', 'third', 'last', 'next', 'previous', 'above', 'below', 'into', 'through', 'before', 'after', 'while', 'during', 'about', 'than', 'then', 'thus'}

def _resolve_anaphor(trigger_kind: str, candidates: Sequence[Tuple[str, str, int]]) -> Tuple[Optional[str], str]:
    pool = [(ent, kind, idx) for ent, kind, idx in candidates if kind in ('phrase', 'acronym', 'noun')]
    if not pool:
        return (None, trigger_kind)
    pool.sort(key=lambda t: (-len(t[0]), -t[2]))
    if trigger_kind == 'ordinal':
        return (pool[0][0], 'ordinal')
    if trigger_kind == 'first':
        return (pool[0][0], 'first')
    if trigger_kind == 'second':
        return (pool[1][0] if len(pool) > 1 else pool[0][0], 'second')
    if trigger_kind == 'third':
        return (pool[2][0] if len(pool) > 2 else pool[0][0], 'third')
    if trigger_kind == 'last':
        return (pool[-1][0], 'last')
    if trigger_kind in ('it', 'them', 'their', 'those', 'they'):
        return (pool[0][0], trigger_kind)
    return (pool[0][0], trigger_kind)

def resolve(question: str, history: Sequence[Dict], *, history_window: int=4) -> ResolverResult:
    q = (question or '').strip()
    if not q:
        return ResolverResult(rewritten_question='', resolved_topics=[], confident_topics=[], ambiguous_resolutions=[])
    trimmed = list(history or [])[-history_window:]
    if not trimmed:
        return ResolverResult(rewritten_question=q, resolved_topics=[], confident_topics=[], ambiguous_resolutions=[])
    candidates = _history_entities(trimmed)
    confident: List[str] = []
    ambiguous: List[str] = []
    rewrites: List[str] = []
    for pattern, kind in ANAPHORIC_TRIGGERS:
        if re.search(pattern, q, re.IGNORECASE):
            topic, rkind = _resolve_anaphor(kind, candidates)
            if topic:
                if rkind in ('ordinal', 'first', 'second', 'third', 'last'):
                    ambiguous.append(f'{rkind}→{topic}')
                else:
                    confident.append(topic)
                rewrites.append(topic)
    if confident or ambiguous:
        seen = set()
        unique = []
        for t in confident + ambiguous:
            k = t.split('→', 1)[0]
            if k.lower() in seen:
                continue
            seen.add(k.lower())
            unique.append(t)
        hint_line = ' (referring to: ' + ', '.join(unique) + ')'
        new_q = q.rstrip('?') + ('.' if not q.endswith('.') else '') + hint_line
    else:
        new_q = q
    return ResolverResult(rewritten_question=new_q, resolved_topics=list(dict.fromkeys(confident + ambiguous)), confident_topics=list(dict.fromkeys([t.lower() for t in confident])), ambiguous_resolutions=list(dict.fromkeys([t.lower() for t in ambiguous])))
