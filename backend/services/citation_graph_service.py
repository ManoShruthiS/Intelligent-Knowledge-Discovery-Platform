from __future__ import annotations
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import httpx
import database.database as db
from services.citations_service import extract_citation_candidates
logger = logging.getLogger(__name__)
ARXIV_API = 'http://export.arxiv.org/api/{id}'
CROSSREF_API = 'https://api.crossref.org/works/{doi}'
OPENALEX_API = 'https://api.openalex.org/works/{id}'
HTTP_TIMEOUT = 8.0
ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1]

def _first_text(elem, path: str) -> Optional[str]:
    for child in elem.iter():
        if _strip_ns(child.tag) == path:
            return (child.text or '').strip() or None
    return None

def _extract_arxiv_id(s: str) -> Optional[str]:
    if not s:
        return None
    m = re.search('(\\d{4}\\.\\d{4,5})(v\\d+)?', s)
    return m.group(0) if m else None

def lookup_arxiv(arxiv_id: str) -> Optional[Dict]:
    arxiv_id = _extract_arxiv_id(arxiv_id) or arxiv_id.strip()
    if not arxiv_id:
        return None
    cached = db.find_citation_reference(arxiv_id=arxiv_id)
    if cached:
        return cached
    url = ARXIV_API.format(id=quote(arxiv_id, safe=''))
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, headers={'User-Agent': 'IKDP/1.0 (mailto:dev@example.com)'})
        if r.status_code != 200:
            logger.warning('arXiv API returned %s for %s', r.status_code, arxiv_id)
            return None
        root = ET.fromstring(r.text)
        entry = None
        for child in root:
            if _strip_ns(child.tag) == 'entry':
                entry = child
                break
        if entry is None:
            return None
        title = _first_text(entry, 'title') or 'Untitled'
        summary = _first_text(entry, 'summary') or None
        year = None
        published = _first_text(entry, 'published') or ''
        if published[:4].isdigit():
            year = int(published[:4])
        authors = []
        for child in entry.iter():
            if _strip_ns(child.tag) == 'author':
                name = _first_text(child, 'name')
                if name:
                    authors.append(name)
        authors_str = ', '.join(authors) if authors else None
        primary_category = entry.find('arxiv:primary_category', ATOM_NS)
        venue = None
        if primary_category is not None:
            venue = f"arXiv ({primary_category.attrib.get('term', '').strip()})"
        else:
            venue = 'arXiv'
        return {'source': 'arxiv', 'title': title, 'authors': authors_str, 'year': year, 'venue': venue, 'arxiv_id': arxiv_id, 'abstract': summary, 'url': f'https://arxiv.org/abs/{arxiv_id}', 'external_id': arxiv_id}
    except Exception as exc:
        logger.warning('arXiv lookup failed for %s: %s', arxiv_id, exc)
        return None

def lookup_doi(doi: str) -> Optional[Dict]:
    if not doi:
        return None
    clean_doi = doi.strip().lower()
    cached = db.find_citation_reference(doi=clean_doi)
    if cached:
        return cached
    url = CROSSREF_API.format(doi=quote(clean_doi, safe='/:'))
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, headers={'User-Agent': 'IKDP/1.0 (mailto:dev@example.com)'})
        if r.status_code != 200:
            logger.warning('Crossref returned %s for DOI %s', r.status_code, doi)
            return None
        body = r.json().get('message') or {}
        title = (body.get('title') or ['Untitled'])[0]
        authors_list = body.get('author') or []
        authors = ', '.join((' '.join(filter(None, [a.get('given', ''), a.get('family', '')])).strip() for a in authors_list)) or None
        issued = body.get('issued', {}).get('date-parts') or []
        year = None
        if issued and issued[0]:
            y = issued[0][0]
            if isinstance(y, int):
                year = y
        container = body.get('container-title') or []
        venue = container[0] if container else None
        citations = body.get('is-referenced-by-count')
        abstract = body.get('abstract')
        if abstract:
            abstract = re.sub('<[^>]+>', '', abstract).strip() or None
        return {'source': 'crossref', 'title': title, 'authors': authors, 'year': year, 'venue': venue, 'doi': clean_doi, 'abstract': abstract, 'citations_count': citations, 'url': body.get('URL') or f'https://doi.org/{clean_doi}', 'external_id': body.get('DOI'), 'metadata': {'type': body.get('type'), 'publisher': body.get('publisher')}}
    except Exception as exc:
        logger.warning('Crossref lookup failed for %s: %s', doi, exc)
        return None

def lookup_openalex(openalex_id: str) -> Optional[Dict]:
    if not openalex_id:
        return None
    openalex_id = openalex_id.strip()
    if openalex_id.startswith('https://'):
        openalex_id = openalex_id.rsplit('/', 1)[-1]
    url = OPENALEX_API.format(id=quote(openalex_id, safe=''))
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, headers={'User-Agent': 'IKDP/1.0 (mailto:dev@example.com)'})
        if r.status_code != 200:
            return None
        work = r.json() or {}
        ids = work.get('ids') or {}
        doi = (ids.get('doi') or '').replace('https://doi.org/', '') or None
        return {'title': work.get('title') or work.get('display_name') or 'Untitled', 'authors': None, 'year': work.get('publication_year'), 'venue': (work.get('primary_location') or {}).get('source', {}).get('display_name'), 'doi': doi, 'citations_count': work.get('cited_by_count'), 'openalex_id': openalex_id, 'url': work.get('doi') or ids.get('doi'), 'external_id': openalex_id}
    except Exception as exc:
        logger.warning('OpenAlex lookup failed for %s: %s', openalex_id, exc)
        return None

class CitationGraphService:

    def build_for_document(self, document_id: str, force: bool=False) -> Dict:
        if not force:
            graph = db.get_citation_graph_for_document(document_id)
            if graph['nodes']:
                return graph
        db.delete_citation_edges_for_document(document_id)
        candidates = extract_citation_candidates(document_id)
        seen_keys = set()
        resolved = 0
        for cand in candidates:
            payload: Optional[Dict] = None
            doi = cand.get('doi')
            arxiv_id = cand.get('arxiv_id') or _extract_arxiv_id(cand.get('title', ''))
            if doi:
                payload = lookup_doi(doi)
            if payload is None and arxiv_id:
                payload = lookup_arxiv(arxiv_id)
            if payload is None:
                payload = {'source': 'heuristic', 'title': cand.get('title') or 'Untitled reference', 'authors': cand.get('authors'), 'year': cand.get('year'), 'venue': cand.get('venue'), 'doi': doi, 'arxiv_id': arxiv_id}
                if not payload.get('title'):
                    continue
            dedup_key = (payload.get('doi'), payload.get('arxiv_id'), payload.get('title', '').lower()[:80])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            payload['metadata'] = {'heuristic': True} if payload.get('source') == 'heuristic' else payload.get('metadata')
            ref = db.upsert_citation_reference(payload)
            db.create_citation_edge(source_document_id=document_id, target_reference_id=ref['id'], relationship='cites', context=cand.get('raw'), page_number=cand.get('page_number'))
            resolved += 1
        graph = db.get_citation_graph_for_document(document_id)
        graph['resolved_count'] = resolved
        graph['total_candidates'] = len(candidates)
        return graph

    def add_reference_manually(self, document_id: str, payload: Dict) -> Dict:
        doi = payload.get('doi')
        arxiv_id = payload.get('arxiv_id') or _extract_arxiv_id(payload.get('title', ''))
        resolved: Optional[Dict] = None
        if doi:
            resolved = lookup_doi(doi)
        if resolved is None and arxiv_id:
            resolved = lookup_arxiv(arxiv_id)
        if resolved is None:
            resolved = {'source': 'manual', **payload}
        else:
            for k in ('title', 'authors', 'year', 'venue'):
                if payload.get(k):
                    resolved[k] = payload[k]
        ref = db.upsert_citation_reference(resolved)
        db.create_citation_edge(source_document_id=document_id, target_reference_id=ref['id'], relationship='cites', context=payload.get('context'), page_number=payload.get('page_number'))
        return db.get_citation_graph_for_document(document_id)

    def find_reference_metadata(self, *, doi: Optional[str]=None, arxiv_id: Optional[str]=None) -> Optional[Dict]:
        if doi:
            ref = lookup_doi(doi)
        elif arxiv_id:
            ref = lookup_arxiv(arxiv_id)
        else:
            return None
        if not ref:
            return None
        return db.upsert_citation_reference(ref)
citation_graph_service = CitationGraphService()
