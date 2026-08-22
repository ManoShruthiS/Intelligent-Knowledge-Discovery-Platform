"""
Discovery services for KNO.

Three independent, free, no-key-required public research sources:
  - OpenAlex  (https://api.openalex.org)      — works of literature
  - Crossref  (https://api.crossref.org)      — DOI / metadata
  - arXiv     (http://export.arxiv.org/api)   — pre-prints (Atom XML)

Each source is called with a polite User-Agent. Network failures are
surfaced as `unavailable` results so the UI can show a graceful message.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "KNO/1.0 (mailto:support@kno.local)"
TIMEOUT = 15.0

ATOM_NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


# ----------------------------------------------------------------------------
# OpenAlex
# ----------------------------------------------------------------------------

def _openalex_search(query: str, limit: int = 10) -> List[Dict]:
    query = (query or "").strip()
    if not query:
        return []
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per_page": max(1, min(25, limit)),
        "select": "id,doi,title,authorships,publication_year,primary_location,open_access,abstract_inverted_index,cited_by_count",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                logger.warning(f"OpenAlex returned {r.status_code}")
                return []
            data = r.json()
    except Exception as e:
        logger.warning(f"OpenAlex request failed: {e}")
        return []
    results = []
    for w in data.get("results", []):
        title = _abstract_openalex(w.get("title"))
        abstract = _reconstruct_abstract_openalex(w.get("abstract_inverted_index"))
        authors = []
        for a in w.get("authorships", []) or []:
            name = ((a.get("author") or {}).get("display_name")) or None
            if name:
                authors.append(name)
        venue = None
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        venue = src.get("display_name") or loc.get("landing_page_url")
        doi = w.get("doi")
        results.append({
            "id": w.get("id"),
            "title": title,
            "authors": authors,
            "year": w.get("publication_year"),
            "venue": venue,
            "doi": (doi.replace("https://doi.org/", "") if isinstance(doi, str) else None),
            "url": (loc.get("landing_page_url") if isinstance(loc, dict) else None) or doi,
            "open_access": bool((w.get("open_access") or {}).get("is_oa")),
            "abstract": abstract,
            "cited_by_count": w.get("cited_by_count"),
            "source": "openalex",
        })
    return results


# OpenAlex stores abstracts as an inverted index; reconstruct.
def _reconstruct_abstract_openalex(inv_index: Optional[Dict]) -> Optional[str]:
    if not inv_index:
        return None
    try:
        positions = []
        for word, locs in inv_index.items():
            for p in locs:
                positions.append((p, word))
        positions.sort()
        return " ".join(w for _, w in positions).strip() or None
    except Exception:
        return None


def _abstract_openalex(t) -> Optional[str]:
    if isinstance(t, list):
        return t[0] if t else None
    return t or None


# ----------------------------------------------------------------------------
# Crossref
# ----------------------------------------------------------------------------

def _crossref_search(query: str, limit: int = 10) -> List[Dict]:
    query = (query or "").strip()
    if not query:
        return []
    url = "https://api.crossref.org/works"
    params = {"query.bibliographic": query, "rows": max(1, min(25, limit))}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            if r.status_code != 200:
                logger.warning(f"Crossref returned {r.status_code}")
                return []
            data = r.json()
    except Exception as e:
        logger.warning(f"Crossref request failed: {e}")
        return []
    items = (data.get("message") or {}).get("items", []) or []
    results = []
    for it in items:
        title_list = it.get("title") or []
        title = title_list[0] if title_list else None
        authors_list = []
        for a in it.get("author") or []:
            fam = a.get("family")
            giv = a.get("given")
            if fam and giv:
                authors_list.append(f"{fam}, {giv}")
            elif fam:
                authors_list.append(fam)
        issued = it.get("issued") or {}
        date_parts = (issued.get("date-parts") or [[None]])[0]
        year = date_parts[0] if date_parts else None
        venue = (it.get("container-title") or [""])[0] if it.get("container-title") else None
        doi = it.get("DOI")
        url_value = it.get("URL")
        results.append({
            "id": doi or url_value or title,
            "title": title,
            "authors": authors_list,
            "year": year,
            "venue": venue,
            "doi": doi,
            "url": url_value,
            "open_access": None,
            "abstract": None,
            "cited_by_count": it.get("is-referenced-by-count"),
            "source": "crossref",
        })
    return results


# ----------------------------------------------------------------------------
# arXiv (Atom XML)
# ----------------------------------------------------------------------------

def _arxiv_search(query: str, limit: int = 10) -> List[Dict]:
    query = (query or "").strip()
    if not query:
        return []
    # Honour arXiv polite 3s rate limit
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max(1, min(25, limit)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                logger.warning(f"arXiv returned {r.status_code}")
                return []
            text = r.text
    except Exception as e:
        logger.warning(f"arXiv request failed: {e}")
        return []

    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        logger.warning(f"arXiv XML parse failed: {e}")
        return []

    results = []
    for entry in root.findall("a:entry", ATOM_NS):
        title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("a:summary", default="", namespaces=ATOM_NS) or "").strip()
        id_full = (entry.findtext("a:id", default="", namespaces=ATOM_NS) or "").strip()
        arxiv_id = id_full.split("/abs/")[-1] if "/abs/" in id_full else id_full

        # Authors
        authors = []
        for au in entry.findall("a:author", ATOM_NS):
            name = (au.findtext("a:name", default="", namespaces=ATOM_NS) or "").strip()
            if name:
                authors.append(name)

        # Year
        published = (entry.findtext("a:published", default="", namespaces=ATOM_NS) or "").strip()
        year = None
        if published and len(published) >= 4:
            try:
                year = int(published[:4])
            except ValueError:
                year = None

        # Categories
        cats = [c.attrib.get("term", "") for c in entry.findall("a:category", ATOM_NS)]

        # DOI sometimes in arxiv:doi
        doi = entry.findtext("arxiv:doi", default=None, namespaces=ATOM_NS)

        results.append({
            "id": arxiv_id,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": "arXiv" + (f" [{', '.join([c for c in cats[:3] if c])}]" if cats else ""),
            "doi": doi,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "open_access": True,
            "abstract": summary[:2000] or None,
            "cited_by_count": None,
            "source": "arxiv",
        })
    return results


# ----------------------------------------------------------------------------
# Unified search
# ----------------------------------------------------------------------------

def search_all(query: str, limit_per_source: int = 8) -> Dict:
    """
    Run all three sources sequentially. Return merged, de-duplicated list
    plus per-source availability flags.
    """
    query = (query or "").strip()
    results_openalex = _openalex_search(query, limit_per_source)
    results_crossref = _crossref_search(query, limit_per_source)
    results_arxiv = _arxiv_search(query, limit_per_source)

    combined: List[Dict] = []
    seen_keys = set()

    def _key(r):
        if r.get("doi"):
            return ("doi", r["doi"].lower())
        if r.get("url"):
            return ("url", r["url"].lower())
        return ("title", (r.get("title") or "").lower())

    for r in results_openalex + results_crossref + results_arxiv:
        k = _key(r)
        if k in seen_keys:
            continue
        seen_keys.add(k)
        combined.append(r)

    return {
        "query": query,
        "combined": combined,
        "by_source": {
            "openalex": results_openalex,
            "crossref": results_crossref,
            "arxiv": results_arxiv,
        },
        "availability": {
            "openalex": "ok" if results_openalex is not None and not _errored(results_openalex) else ("unavailable" if not results_openalex else "ok"),
            "crossref": "ok" if results_crossref else "unavailable",
            "arxiv": "ok" if results_arxiv else "unavailable",
        },
        "total": len(combined),
    }


def _errored(results) -> bool:
    # placeholder hook in case we later surface per-source error flags
    return False


# ----------------------------------------------------------------------------
# Sync wrapper for FastAPI route handlers
# ----------------------------------------------------------------------------

def search_research(query: str, limit_per_source: int = 8) -> Dict:
    return search_all(query, limit_per_source)
