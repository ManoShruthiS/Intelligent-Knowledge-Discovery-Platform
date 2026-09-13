import re
from typing import Dict, List, Optional
import database.database as db
YEAR_RE = re.compile('(19|20)\\d{2}')
ARXIV_RE = re.compile('arXiv\\s*[:\\.]\\s*(\\d{4}\\.\\d{4,5}(v\\d+)?)', re.IGNORECASE)
DOI_RE = re.compile('(?:doi[:\\s]*|https?://(?:dx\\.)?doi\\.org/)(10\\.\\d{3,9}/[^\\s,;)]+)', re.IGNORECASE)

def _truncate_at(s: str, n: int=600) -> str:
    return s if len(s) <= n else s[:n] + '…'

def extract_citation_candidates(document_id: str) -> List[Dict]:
    doc = db.get_document_by_id(document_id)
    if not doc:
        return []
    chunks = db.get_chunks_for_document(document_id)
    candidates: List[Dict] = []
    seen_keys: set = set()
    RE_HEAD = re.compile("(?m)^\\s*(?:\\[\\d+\\]|\\d+\\.|\\(\\d+\\))?\\s*([A-Z][A-Za-zÀ-ž\\-\\.\\']+(?:,\\s*[A-Z]\\.\\s*[A-Za-zÀ-ž\\-\\.\\']+){0,4})")
    for chunk in chunks:
        text = chunk.get('text', '') or ''
        for line in text.splitlines():
            line = line.strip()
            if not line or len(line) < 25 or len(line) > 600:
                continue
            if not RE_HEAD.match(line):
                continue
            doi_m = DOI_RE.search(line)
            doi = doi_m.group(1).rstrip('.') if doi_m else None
            arxiv_m = ARXIV_RE.search(line)
            arxiv_id = arxiv_m.group(1) if arxiv_m else None
            year_m = YEAR_RE.search(line)
            year = int(year_m.group(0)) if year_m else None
            title = None
            if year:
                parts = line.split(str(year), 1)
                if len(parts) == 2:
                    tail = parts[1].lstrip(',. ').rstrip('.')
                    words = tail.split()
                    title_words = []
                    for w in words[:14]:
                        title_words.append(w)
                        if w.endswith('.') and len(title_words) >= 4:
                            break
                    if title_words:
                        title = ' '.join(title_words).rstrip(',.;: ')
                        title = title.rstrip(',.')
                        if not 20 <= len(title) <= 300:
                            title = None
            if not title:
                title = line[:200].rstrip()
            key = line[:40].lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append({'document_id': document_id, 'title': title, 'authors': None, 'year': year, 'venue': None, 'doi': doi, 'url': f'https://doi.org/{doi}' if doi else f'https://arxiv.org/abs/{arxiv_id}' if arxiv_id else None, 'arxiv_id': arxiv_id, 'raw': _truncate_at(line, 400), 'source_type': 'extracted'})
            if len(candidates) >= 50:
                return candidates
    return candidates

def list_citations(workspace_id: Optional[str]=None) -> List[Dict]:
    return db.list_citations(workspace_id=workspace_id)

def create_citation(data: Dict) -> Dict:
    return db.create_citation(**data)

def delete_citation(cite_id: str) -> bool:
    return db.delete_citation(cite_id)

def _join_authors_apa(authors: List[str]) -> str:
    if not authors:
        return ''
    formatted = []
    for a in authors:
        a = a.strip()
        if not a:
            continue
        if ',' in a:
            last, first = [x.strip() for x in a.split(',', 1)]
            initials = ' '.join((p[0] + '.' for p in first.split() if p))
            formatted.append(f'{last}, {initials}')
        else:
            parts = a.split()
            if len(parts) >= 2:
                last = parts[-1]
                initials = ' '.join((p[0] + '.' for p in parts[:-1] if p))
                formatted.append(f'{last}, {initials}')
            else:
                formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f'{formatted[0]} & {formatted[1]}'
    return ', '.join(formatted[:-1]) + ', & ' + formatted[-1]

def _join_authors_ieee(authors: List[str]) -> str:
    if not authors:
        return ''
    formatted = []
    for a in authors:
        a = a.strip()
        if not a:
            continue
        if ',' in a:
            last, first = [x.strip() for x in a.split(',', 1)]
            initials = ' '.join((p[0] + '.' for p in first.split() if p))
            formatted.append(f'{initials} {last}'.strip())
        else:
            parts = a.split()
            if len(parts) >= 2:
                last = parts[-1]
                initials = ' '.join((p[0] + '.' for p in parts[:-1] if p))
                formatted.append(f'{initials} {last}'.strip())
            else:
                formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f'{formatted[0]} and {formatted[1]}'
    return ', '.join(formatted[:-1]) + ', and ' + formatted[-1]

def _split_authors_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = re.split(';|(?<![\\w]),\\s*(?=[A-Z])', raw)
    return [p.strip() for p in parts if p.strip()]

def _split_first_author_last_name(authors_str: str) -> str:
    for a in _split_authors_list(authors_str):
        if ',' in a:
            return a.split(',', 1)[0].strip()
        parts = a.split()
        return parts[-1] if parts else a
    return ''

def format_ieee(c: Dict) -> str:
    authors = _split_authors_list(c.get('authors'))
    title = (c.get('title') or '').strip().rstrip('.')
    venue = (c.get('venue') or '').strip().rstrip('.')
    year = c.get('year')
    doi = c.get('doi')
    url = c.get('url')
    parts = []
    if authors:
        parts.append(_join_authors_ieee(authors))
    if title:
        parts.append(f'"{title}."')
    if venue:
        parts.append(venue)
    if year:
        parts.append(str(year))
    base = ', '.join([p for p in parts if p]) + '.'
    if doi:
        base += f' doi:{doi}.'
    elif url:
        base += f' [Online]. Available: {url}'
    return base

def format_apa(c: Dict) -> str:
    authors = _split_authors_list(c.get('authors'))
    title = (c.get('title') or '').strip().rstrip('.')
    venue = (c.get('venue') or '').strip().rstrip('.')
    year = c.get('year')
    doi = c.get('doi')
    url = c.get('url')
    parts = []
    if authors:
        parts.append(_join_authors_apa(authors) + ('.' if not _join_authors_apa(authors).endswith('.') else ''))
    if year:
        parts.append(f'({year}).')
    if title:
        parts.append(title + '.')
    if venue:
        if venue:
            parts.append(f'_{venue}_.' if not venue.lower().startswith('arxiv') else f'{venue}.')
    if doi:
        parts.append(f'https://doi.org/{doi}')
    elif url:
        parts.append(url)
    return ' '.join(parts)

def format_mla(c: Dict) -> str:
    authors_str = c.get('authors') or ''
    title = (c.get('title') or '').strip().rstrip('.')
    venue = (c.get('venue') or '').strip().rstrip('.')
    year = c.get('year')
    doi = c.get('doi')
    url = c.get('url')
    authors = _split_authors_list(authors_str)
    if authors:
        if len(authors) == 1:
            first = authors[0]
            if ',' in first:
                last, given = [x.strip() for x in first.split(',', 1)]
                first = f'{last}, {given}'
            author_part = first + '.'
        elif len(authors) == 2:
            first = authors[0]
            if ',' in first:
                last, given = [x.strip() for x in first.split(',', 1)]
                first = f'{last}, {given}'
            author_part = f'{first}, and {authors[1]}.'
        else:
            first = authors[0]
            if ',' in first:
                last, given = [x.strip() for x in first.split(',', 1)]
                first = f'{last}, {given}'
            author_part = f'{first}, et al.'
    else:
        author_part = ''
    bits = []
    if author_part:
        bits.append(author_part)
    if title:
        bits.append(f'"{title}."')
    if venue:
        bits.append(f'_{venue}_,')
    if year:
        bits.append(f'{year}.')
    if doi:
        bits.append(f'doi:{doi}.')
    elif url:
        bits.append(url.rstrip('.') + '.')
    return ' '.join(bits)

def format_chicago(c: Dict) -> str:
    authors = _split_authors_list(c.get('authors'))
    title = (c.get('title') or '').strip().rstrip('.')
    venue = (c.get('venue') or '').strip().rstrip('.')
    year = c.get('year')
    doi = c.get('doi')
    url = c.get('url')
    if not authors:
        author_part = ''
    elif len(authors) == 1:
        a = authors[0]
        if ',' in a:
            last, given = [x.strip() for x in a.split(',', 1)]
            author_part = f'{last}, {given}'
        else:
            author_part = a
    else:
        first = authors[0]
        if ',' in first:
            last, given = [x.strip() for x in first.split(',', 1)]
            first = f'{last}, {given}'
        author_part = f'{first} et al.'
    bits = []
    if author_part:
        bits.append(author_part + '.')
    if year:
        bits.append(f'{year}.')
    if title:
        bits.append(f'"{title}."')
    if venue:
        bits.append(f'{venue}.')
    if doi:
        bits.append(f'https://doi.org/{doi}.')
    elif url:
        bits.append(url)
    return ' '.join(bits)

def format_bibtex(c: Dict) -> str:
    authors_str = c.get('authors') or ''
    title = (c.get('title') or 'Untitled').strip()
    year = c.get('year') or ''
    venue = (c.get('venue') or '').strip()
    doi = c.get('doi')
    first_author_last = _split_first_author_last_name(authors_str) or 'unknown'
    first_word = re.sub('[^A-Za-z0-9]', '', first_author_last.lower()) or 'ref'
    key = f'{first_word}{year}' if year else first_word
    suffix = (c.get('external_id') or c.get('id') or '')[:6]
    if suffix:
        key += suffix.lower().replace('-', '')
    bib_type = 'article' if venue else 'misc'
    lines = [f'@{bib_type}{{{key},']
    lines.append(f'  title   = {{{title}}},')
    if authors_str:
        lines.append(f'  author  = {{{authors_str}}},')
    if venue:
        lines.append(f'  journal = {{{venue}}},')
    if year:
        lines.append(f'  year    = {{{year}}},')
    if doi:
        lines.append(f'  doi     = {{{doi}}},')
    lines.append('}')
    return '\n'.join(lines)
RIS_TYPE_MAP = {'journalArticle': 'JOUR', 'article': 'JOUR', 'conferencePaper': 'CONF', 'book': 'BOOK', 'bookChapter': 'CHAP', 'thesis': 'THES', 'report': 'RPRT', 'misc': 'GEN', 'webpage': 'ELEC', 'preprint': 'GEN'}

def format_ris(c: Dict) -> str:
    authors_str = (c.get('authors') or '').strip()
    title = (c.get('title') or 'Untitled').strip()
    year = c.get('year')
    venue = (c.get('venue') or '').strip()
    doi = c.get('doi')
    url = c.get('url')
    abstract = c.get('abstract')
    source_type = (c.get('source_type') or '').strip()
    ris_type = RIS_TYPE_MAP.get(source_type, 'GEN')
    lines = [f'TY  - {ris_type}']
    if title:
        lines.append(f'TI  - {title}')
    if authors_str:
        for author in _split_authors_list(authors_str):
            lines.append(f'AU  - {author}')
    if year:
        try:
            lines.append(f'PY  - {int(year)}')
        except (TypeError, ValueError):
            pass
    if venue:
        lines.append(f'JO  - {venue}')
    if doi:
        lines.append(f'DO  - {doi}')
    if url:
        lines.append(f'UR  - {url}')
    if abstract:
        lines.append(f'AB  - {abstract}')
    lines.append('ER  - ')
    return '\n'.join(lines)

def format_bibliography(citations: List[Dict], style: str) -> str:
    if not citations:
        return ''
    style = (style or '').lower()
    if style == 'bibtex':
        return '\n\n'.join((format_bibtex(c) for c in citations))
    if style == 'ris':
        return '\n'.join((format_ris(c) for c in citations)) + '\n'
    return '\n\n'.join((format_citation(c, style) for c in citations))
FORMATTERS = {'ieee': format_ieee, 'apa': format_apa, 'mla': format_mla, 'chicago': format_chicago, 'bibtex': format_bibtex, 'ris': format_ris}

def format_citation(c: Dict, style: str) -> str:
    fmt = FORMATTERS.get((style or '').lower())
    if not fmt:
        fmt = format_ieee
    return fmt(c)

def citation_filename(style: str) -> str:
    s = (style or '').lower()
    return {'bibtex': 'bibliography.bib', 'ris': 'bibliography.ris'}.get(s, f"bibliography.{s or 'txt'}")
