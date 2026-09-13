from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import logging
logger = logging.getLogger(__name__)
INTENT_PATTERNS: List[Tuple[str, List[str]]] = [('section', ['\\bpage\\s+\\d+\\b', '\\bpages?\\s+\\d+\\s*(?:to|-|–|through|to|and)\\s*\\d+\\b', '\\bsection\\s+[a-z0-9]+(\\.\\d+)?\\b', '\\bchapter\\s+\\d+\\b', '\\btable\\s+(?:of\\s+contents\\s+)?(\\d+|[ivx]+)\\b', '\\bfigure\\s+\\d+\\b', '\\bon\\s+page\\s+\\d+\\b', '\\bappendix\\b']), ('comparison', ['\\bcompare\\b', '\\bcomparing\\b', '\\bcomparison\\b', '\\bdiffer(ence|ences|ent)?\\b', '\\bversus\\b', '\\bvs\\.?\\b', '\\bbetween\\b.+\\band\\b', '\\bcontrast\\b', '\\bsame\\s+(?:as|with)\\b', '\\bbetter\\b.+\\bthan\\b', '\\bworse\\b.+\\bthan\\b']), ('how_to', ['\\bhow\\s+(?:do|can|should|would|to|does|is|are)\\b', '\\bsteps?\\b', '\\bprocedure\\b', '\\bworkflow\\b', '\\bprocess\\b', '\\bset\\s*up\\b', '\\bimplement\\b', '\\bapply\\b']), ('data', ['\\bdatasets?\\b', '\\bbenchmarks?\\b', '\\bresults?\\b', '\\bscore\\b', '\\baccuracy\\b', '\\bprecision\\b', '\\brecall\\b', '\\bF1\\b', '\\bMETEOR\\b', '\\bBLEU\\b', '\\bROUGE\\b', '\\bperplexity\\b', '\\bmetrics?\\b', '\\bnumbers?\\b', '\\bpercentage\\b', '\\bbaseline\\b', '\\bstate-of-the-art\\b', '\\bSOTA\\b', '\\bresults?\\s+(?:on|of|for|achieved|are|were)\\b']), ('method', ['\\bmethod(?:ology|ologies|s)?\\b', '\\bapproach(es)?\\b', '\\btechnique\\b', '\\balgorithm\\b', '\\bframework\\b', '\\bmethod(?:s)?\\b', '\\barchitecture\\b', '\\bpipeline\\b', '\\bpreprocess(?:ing)?\\b', '\\blookup\\b', '\\bretrieval\\b', '\\bencoding\\b', '\\bfine-?tun(?:e|ing)\\b', '\\bstep\\b']), ('findings', ['\\bfinding(s)?\\b', '\\boutcomes?\\b', '\\bconclusions?\\b', '\\bresults?\\s+(?:of|from|in|demonstrate|show|reveal)\\b', '\\bdiscover(?:ed|y|ies)?\\b', '\\bclaim(s)?\\b', '\\bshows?\\s+that\\b', '\\bsuggesting?\\b', '\\bimplies?\\b', '\\bimprovements?\\b', '\\boutperform(s|ed)?\\b']), ('explanation', ['\\bwhy\\b', '\\bexplain\\b', '\\bhow\\s+does\\b.+\\bwork\\b', '\\bhow\\s+do\\b.+\\bwork\\b', '\\bmechanism\\b', '\\breason\\b', '\\bimportance\\b', '\\bsignificance\\b', '\\bpurpose\\b']), ('definition', ['\\bwhat\\s+(?:is|are)\\s+(?:a|an|the)?\\s*[\\w][\\w\\s-]{0,80}\\??\\s*$', '\\bdefine\\b', '\\bdefinition\\s+of\\b', '\\bwhat\\s+does\\b.+\\bmean\\b', '\\bmeaning\\b'])]
GENERAL_PATTERNS: List[str] = ['\\?$', '^(?:what|how|why|when|where|who|which)\\b', '\\?']

def classify_intent(question: str) -> str:
    q = (question or '').strip()
    if not q:
        return 'general'
    scored: List[Tuple[str, int, int]] = []
    for pos, (intent, patterns) in enumerate(INTENT_PATTERNS):
        hits = 0
        for pat in patterns:
            if re.search(pat, q, re.IGNORECASE):
                hits += 1
        if hits > 0:
            scored.append((intent, hits, pos))
    if not scored:
        for pat in GENERAL_PATTERNS:
            if re.search(pat, q):
                return 'general'
        return 'general'
    scored.sort(key=lambda t: (-t[1], t[2]))
    return scored[0][0]
STOP_WORDS = {'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'these', 'those', 'it', 'its', 'i', 'you', 'he', 'she', 'we', 'they', 'them', 'my', 'your', 'our', 'their', 'his', 'her', 'what', 'how', 'why', 'when', 'where', 'who', 'which', 'do', 'does', 'did', 'would', 'could', 'should', 'shall', 'may', 'might', 'must', 'can', 'tell', 'explain', 'describe', 'show', 'give', 'list', 'find', 'between', 'compare', 'use', 'used', 'using', 'having', 'have', 'has', 'had', 'make', 'makes', 'made', 'got', 'get', 'getting', 'need', 'needs', 'needed', 'more', 'most', 'much', 'many', 'very', 'such', 'some', 'any', 'all', 'each', 'every', 'first', 'second', 'third', 'last', 'next', 'previous', 'above', 'below', 'between', 'into', 'through', 'before', 'after', 'while', 'during', 'about', 'than', 'then', 'thus'}
COMMON_ACRONYMS = {'ai', 'ml', 'nlp', 'llm', 'rag', 'pdf', 'url', 'api', 'cli', 'ui', 'ux', 'qa', 'rl', 'sft', 'rlhf', 'dpo', 'knn', 'svm', 'bert', 'gpt', 'llama', 't5', 'vae', 'gan', 'cnn', 'rnn', 'lstm', 'gru', 'xgb', 'cv', 'nli', 'qa', 'tts', 'asr'}
PAGE_RE = re.compile('\\bpage\\s+(\\d+)\\b', re.IGNORECASE)
YEAR_RE = re.compile('\\b(19|20)\\d{2}\\b')
SECTION_RE = re.compile('\\b(section|chapter|appendix|figure|table)\\s+([\\w\\.]+)\\b', re.IGNORECASE)

def extract_entities(question: str) -> List[str]:
    q = question or ''
    entities: List[str] = []
    seen = set()
    SENTENCE_LEADING_VERBS = {'tell', 'show', 'list', 'find', 'get', 'fetch', 'describe', 'explain', 'compare', 'define', 'summarize', 'give', 'use', 'provide', 'identify', 'name', 'say', 'explain', 'elaborate'}

    def add(s: str) -> None:
        s = s.strip()
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        if key in STOP_WORDS or key in SENTENCE_LEADING_VERBS or len(key) < 2:
            return
        seen.add(key)
        entities.append(s)
    for m in re.finditer('(?<![\\w])([A-Z][A-Za-z0-9]+(?:[-–][A-Z][A-Za-z0-9]+)*(?:\\s+[A-Z][a-zA-Z]+)*)', q):
        phrase = m.group(1).strip().replace('–', '-')
        if phrase and phrase.lower() not in STOP_WORDS and (phrase.lower() not in SENTENCE_LEADING_VERBS):
            add(phrase)
    for m in re.finditer('\\b([A-Z]{2,}|[A-Z]\\d[A-Z0-9]*)\\b', q):
        add(m.group(1))
    for token in re.findall('\\b([a-z]{2,5})\\b', q.lower()):
        if token in COMMON_ACRONYMS:
            add(token.upper())
    for m in YEAR_RE.finditer(q):
        add(m.group(0))
    for m in PAGE_RE.finditer(q):
        add(m.group(0))
    for m in SECTION_RE.finditer(q):
        add(m.group(0))
    return entities
PAGE_RANGE_RE = re.compile('\\bpage(?:s)?\\s+(\\d+)\\s*(?:[-–]\\s*(\\d+))?\\b', re.IGNORECASE)
YEAR_RANGE_RE = re.compile('\\b(19|20)\\d{2}\\s*(?:[-–]\\s*(19|20)?(\\d{2}))?\\b')

def detect_constraints(question: str) -> Dict:
    q = question or ''
    out: Dict = {'pages': None, 'years': None, 'file_type': None}
    pg_match = PAGE_RANGE_RE.search(q)
    if pg_match:
        try:
            start = int(pg_match.group(1))
            end = int(pg_match.group(2)) if pg_match.group(2) else start
            out['pages'] = (min(start, end), max(start, end))
        except (TypeError, ValueError):
            pass
    years = sorted({int(m.group(0)) for m in YEAR_RE.finditer(q) if m.group(0).isdigit() or m.group(0)[2:].isdigit()})
    if years:
        out['years'] = (min(years), max(years))
    ft_match = re.search('\\.(pdf|docx|txt|md|csv|json|xlsx|pptx)\\b', q.lower())
    if ft_match:
        out['file_type'] = ft_match.group(1)
    return out
INTENT_TOP_K = {'section': 4, 'definition': 4, 'how_to': 5, 'comparison': 8, 'data': 8, 'findings': 6, 'method': 6, 'explanation': 5, 'general': 5}

def choose_top_k(intent: str, *, user_top_k: Optional[int]=None) -> int:
    if user_top_k is not None:
        return user_top_k
    return INTENT_TOP_K.get(intent, INTENT_TOP_K['general'])

@dataclass
class QuestionAnalysis:
    intent: str = 'general'
    entities: List[str] = field(default_factory=list)
    constraints: Dict = field(default_factory=dict)
    rewritten_question: str = ''
    top_k: int = 5
    needs_broad_recall: bool = False

    def has_page_constraint(self) -> bool:
        return bool(self.constraints.get('pages'))

    def summary(self) -> str:
        parts = [f'intent={self.intent}', f'top_k={self.top_k}']
        if self.entities:
            parts.append('entities=' + ','.join(self.entities[:5]))
        if self.has_page_constraint():
            parts.append('pages=' + str(self.constraints['pages']))
        if self.constraints.get('years'):
            parts.append('years=' + str(self.constraints['years']))
        if self.constraints.get('file_type'):
            parts.append('file_type=' + self.constraints['file_type'])
        return '; '.join(parts)

def analyse(question: str, *, user_top_k: Optional[int]=None) -> QuestionAnalysis:
    intent = classify_intent(question)
    entities = extract_entities(question)
    constraints = detect_constraints(question)
    top_k = choose_top_k(intent, user_top_k=user_top_k)
    needs_broad = intent in ('comparison', 'data', 'method', 'findings')
    return QuestionAnalysis(intent=intent, entities=entities, constraints=constraints, top_k=top_k, needs_broad_recall=needs_broad, rewritten_question=(question or '').strip())
if __name__ == '__main__':
    SAMPLES = ['What is RAG-Token?', 'How does the retrieval step work?', 'What datasets were used in the experiments?', 'Compare RAG-Sequence and RAG-Token.', 'Explain the methodology on page 5.', 'What does the second approach propose?', 'List the steps to fine-tune BERT.', 'Who is the third author?', "What's the accuracy on Natural Questions?"]
    for q in SAMPLES:
        a = analyse(q)
        print(f'Q: {q!r}')
        print(f'   intent={a.intent}  top_k={a.top_k}  entities={a.entities}  constraints={a.constraints}')
        print()
