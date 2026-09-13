import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
import httpx
logger = logging.getLogger(__name__)
USER_AGENT = 'KNO/1.0 (mailto:support@kno.local)'
TIMEOUT = 15.0
ATOM_NS = {'a': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

def _normalize_title(t: str) -> str:
    if not t:
        return ''
    t = t.lower()
    t = re.sub('[^a-z0-9 ]', ' ', t)
    t = re.sub('\\s+', ' ', t).strip()
    return t

def _relevance_score(item: Dict, query_words: List[str]) -> float:
    score = 0.0
    title = _normalize_title(item.get('title') or '')
    abstract = (item.get('abstract') or '').lower()
    title_hits = sum((1 for w in query_words if w in title))
    abstract_hits = sum((1 for w in query_words if w in abstract))
    if query_words:
        score += 0.5 * (title_hits / len(query_words))
        score += 0.2 * min(abstract_hits / len(query_words), 1.0)
    year = item.get('year')
    if isinstance(year, int) and year >= 2019:
        score += 0.15 * min((year - 2018) / 6, 1.0)
    citations = item.get('cited_by_count') or 0
    if citations > 0:
        import math
        score += 0.15 * min(math.log10(citations + 1) / 5, 1.0)
    return round(min(score, 1.0), 3)

def _extract_keywords(results: List[Dict], query: str, max_kw: int=15) -> List[str]:
    stop = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'for', 'to', 'with', 'by', 'from', 'at', 'is', 'are', 'was', 'were', 'be', 'been', 'has', 'have', 'had', 'this', 'that', 'these', 'those', 'its', 'it', 'as', 'not', 'but', 'using', 'based', 'via', 'towards', 'approach', 'method', 'model', 'system', 'paper', 'work', 'study', 'novel', 'new', 'deep', 'learning', 'neural', 'network', 'data', 'result', 'results', 'performance', 'evaluation', 'analysis', 'proposed', 'using', 'can', 'we', 'our', 'show', 'shows', 'large', 'high', 'multi', 'pre', 'training', 'fine'}
    freq: Dict[str, int] = {}
    for r in results:
        title = _normalize_title(r.get('title') or '')
        for word in title.split():
            if len(word) > 3 and word not in stop:
                freq[word] = freq.get(word, 0) + 1
    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_kw[:max_kw]]

def _openalex_search(query: str, limit: int=10) -> Tuple[List[Dict], str]:
    query = (query or '').strip()
    if not query:
        return ([], 'ok')
    url = 'https://api.openalex.org/works'
    params = {'search': query, 'per_page': max(1, min(25, limit)), 'select': 'id,doi,title,authorships,publication_year,primary_location,open_access,abstract_inverted_index,cited_by_count,concepts'}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={'User-Agent': USER_AGENT})
            if r.status_code != 200:
                logger.warning(f'OpenAlex returned {r.status_code}')
                return ([], f'error:{r.status_code}')
            data = r.json()
    except Exception as e:
        logger.warning(f'OpenAlex request failed: {e}')
        return ([], 'unavailable')
    results = []
    for w in data.get('results', []):
        title = w.get('title')
        if isinstance(title, list):
            title = title[0] if title else None
        abstract = _reconstruct_abstract(w.get('abstract_inverted_index'))
        authors = []
        for a in w.get('authorships') or []:
            name = (a.get('author') or {}).get('display_name')
            if name:
                authors.append(name)
        loc = w.get('primary_location') or {}
        src = loc.get('source') or {}
        venue = src.get('display_name') or None
        doi = w.get('doi')
        if isinstance(doi, str):
            doi = doi.replace('https://doi.org/', '')
        keywords = [c.get('display_name') for c in (w.get('concepts') or [])[:6] if c.get('display_name') and c.get('score', 0) > 0.3]
        results.append({'id': w.get('id'), 'title': title, 'authors': authors, 'year': w.get('publication_year'), 'venue': venue, 'doi': doi, 'url': loc.get('landing_page_url') or (f'https://doi.org/{doi}' if doi else None), 'pdf_url': loc.get('pdf_url') if isinstance(loc, dict) else None, 'open_access': bool((w.get('open_access') or {}).get('is_oa')), 'abstract': abstract, 'cited_by_count': w.get('cited_by_count'), 'keywords': keywords, 'source': 'openalex'})
    return (results, 'ok')

def _reconstruct_abstract(inv_index: Optional[Dict]) -> Optional[str]:
    if not inv_index:
        return None
    try:
        positions = []
        for word, locs in inv_index.items():
            for p in locs:
                positions.append((p, word))
        positions.sort()
        return ' '.join((w for _, w in positions)).strip() or None
    except Exception:
        return None

def _crossref_search(query: str, limit: int=10) -> Tuple[List[Dict], str]:
    query = (query or '').strip()
    if not query:
        return ([], 'ok')
    url = 'https://api.crossref.org/works'
    params = {'query.bibliographic': query, 'rows': max(1, min(25, limit))}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
            if r.status_code != 200:
                logger.warning(f'Crossref returned {r.status_code}')
                return ([], f'error:{r.status_code}')
            data = r.json()
    except Exception as e:
        logger.warning(f'Crossref request failed: {e}')
        return ([], 'unavailable')
    items = (data.get('message') or {}).get('items', []) or []
    results = []
    for it in items:
        title_list = it.get('title') or []
        title = title_list[0] if title_list else None
        authors_list = []
        for a in it.get('author') or []:
            fam = a.get('family')
            giv = a.get('given')
            if fam and giv:
                authors_list.append(f'{fam}, {giv}')
            elif fam:
                authors_list.append(fam)
        issued = it.get('issued') or {}
        date_parts = (issued.get('date-parts') or [[None]])[0]
        year = date_parts[0] if date_parts else None
        venue = (it.get('container-title') or [''])[0] if it.get('container-title') else None
        doi = it.get('DOI')
        url_val = it.get('URL')
        keywords = [s for s in (it.get('subject') or [])[:6] if s]
        results.append({'id': doi or url_val or title, 'title': title, 'authors': authors_list, 'year': year, 'venue': venue, 'doi': doi, 'url': url_val, 'pdf_url': None, 'open_access': None, 'abstract': None, 'cited_by_count': it.get('is-referenced-by-count'), 'keywords': keywords, 'source': 'crossref'})
    return (results, 'ok')

def _arxiv_search(query: str, limit: int=10) -> Tuple[List[Dict], str]:
    query = (query or '').strip()
    if not query:
        return ([], 'ok')
    url = 'https://export.arxiv.org/api/query'
    params = {'search_query': f'all:{query}', 'start': 0, 'max_results': max(1, min(25, limit)), 'sortBy': 'relevance', 'sortOrder': 'descending'}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={'User-Agent': USER_AGENT})
            if r.status_code != 200:
                logger.warning(f'arXiv returned {r.status_code}')
                return ([], f'error:{r.status_code}')
            text = r.text
    except Exception as e:
        logger.warning(f'arXiv request failed: {e}')
        return ([], 'unavailable')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        logger.warning(f'arXiv XML parse failed: {e}')
        return ([], 'error:xml_parse')
    results = []
    for entry in root.findall('a:entry', ATOM_NS):
        title = (entry.findtext('a:title', default='', namespaces=ATOM_NS) or '').strip()
        title = re.sub('\\s+', ' ', title)
        summary = (entry.findtext('a:summary', default='', namespaces=ATOM_NS) or '').strip()
        id_full = (entry.findtext('a:id', default='', namespaces=ATOM_NS) or '').strip()
        arxiv_id = id_full.split('/abs/')[-1] if '/abs/' in id_full else id_full
        authors = []
        for au in entry.findall('a:author', ATOM_NS):
            name = (au.findtext('a:name', default='', namespaces=ATOM_NS) or '').strip()
            if name:
                authors.append(name)
        published = (entry.findtext('a:published', default='', namespaces=ATOM_NS) or '').strip()
        year = None
        if published and len(published) >= 4:
            try:
                year = int(published[:4])
            except ValueError:
                pass
        cats = [c.attrib.get('term', '') for c in entry.findall('a:category', ATOM_NS)]
        doi = entry.findtext('arxiv:doi', default=None, namespaces=ATOM_NS)
        results.append({'id': arxiv_id, 'title': title, 'authors': authors, 'year': year, 'venue': 'arXiv' + (f" [{', '.join([c for c in cats[:3] if c])}]" if cats else ''), 'doi': doi, 'url': f'https://arxiv.org/abs/{arxiv_id}', 'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf', 'open_access': True, 'abstract': summary[:2000] or None, 'cited_by_count': None, 'keywords': [c for c in cats[:6] if c], 'source': 'arxiv'})
    return (results, 'ok')

def search_research(query: str, limit_per_source: int=10, sort_by: str='relevance', year_from: Optional[int]=None, year_to: Optional[int]=None, open_access_only: bool=False, min_citations: int=0, page: int=1, page_size: int=20) -> Dict:
    query = (query or '').strip()
    t_start = time.monotonic()
    source_results: Dict[str, Tuple[List[Dict], str]] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_openalex_search, query, limit_per_source): 'openalex', pool.submit(_crossref_search, query, limit_per_source): 'crossref', pool.submit(_arxiv_search, query, limit_per_source): 'arxiv'}
        for future in as_completed(futures):
            src = futures[future]
            try:
                results, status = future.result()
                source_results[src] = (results, status)
            except Exception as e:
                logger.error(f'Source {src} future raised: {e}')
                source_results[src] = ([], 'unavailable')
    availability = {src: status for src, (_, status) in source_results.items()}
    all_results: List[Dict] = []
    for src in ('openalex', 'crossref', 'arxiv'):
        results, _ = source_results.get(src, ([], 'unavailable'))
        all_results.extend(results)
    total_raw = len(all_results)
    seen_doi: set = set()
    seen_title: set = set()
    deduped: List[Dict] = []
    for r in all_results:
        doi = (r.get('doi') or '').strip().lower()
        norm_title = _normalize_title(r.get('title') or '')[:80]
        if doi and doi in seen_doi:
            continue
        if not doi and norm_title and (norm_title in seen_title):
            continue
        if doi:
            seen_doi.add(doi)
        if norm_title:
            seen_title.add(norm_title)
        deduped.append(r)
    query_words = [w for w in _normalize_title(query).split() if len(w) > 2]
    filtered = deduped
    if year_from:
        filtered = [r for r in filtered if r.get('year') is None or (r.get('year') or 0) >= year_from]
    if year_to:
        filtered = [r for r in filtered if r.get('year') is None or (r.get('year') or 9999) <= year_to]
    if open_access_only:
        filtered = [r for r in filtered if r.get('open_access')]
    if min_citations > 0:
        filtered = [r for r in filtered if (r.get('cited_by_count') or 0) >= min_citations]
    for r in filtered:
        r['relevance_score'] = _relevance_score(r, query_words)
    if sort_by == 'newest':
        filtered.sort(key=lambda r: r.get('year') or 0, reverse=True)
    elif sort_by == 'oldest':
        filtered.sort(key=lambda r: r.get('year') or 9999)
    elif sort_by == 'citations':
        filtered.sort(key=lambda r: r.get('cited_by_count') or 0, reverse=True)
    else:
        filtered.sort(key=lambda r: r.get('relevance_score', 0), reverse=True)
    total_filtered = len(filtered)
    offset = (page - 1) * page_size
    page_results = filtered[offset:offset + page_size]
    keywords = _extract_keywords(deduped, query)
    elapsed = round(time.monotonic() - t_start, 2)
    return {'query': query, 'combined': page_results, 'total_raw': total_raw, 'total_unique': total_filtered, 'page': page, 'page_size': page_size, 'has_more': offset + page_size < total_filtered, 'elapsed_seconds': elapsed, 'sources_searched': len([s for s, st in availability.items() if st == 'ok']), 'availability': availability, 'keywords': keywords}

def search_all(query: str, limit_per_source: int=8) -> Dict:
    return search_research(query, limit_per_source)
