import logging
from typing import Dict, List
import httpx
logger = logging.getLogger(__name__)
TIMEOUT = 12.0
HF_API = 'https://huggingface.co/api/datasets'

def _hf_search(query: str, limit: int=10) -> List[Dict]:
    query = (query or '').strip()
    if not query:
        return []
    params = {'search': query, 'limit': max(1, min(30, limit))}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(HF_API, params=params, headers={'Accept': 'application/json'})
            if r.status_code != 200:
                logger.warning(f'HuggingFace datasets returned {r.status_code}')
                return []
            data = r.json()
    except Exception as e:
        logger.warning(f'HuggingFace datasets request failed: {e}')
        return []
    results: List[Dict] = []
    for d in data or []:
        results.append({'id': d.get('id'), 'description': None, 'downloads': d.get('downloads'), 'likes': d.get('likes'), 'tags': d.get('tags') or [], 'last_modified': d.get('lastModified'), 'url': f"https://huggingface.co/datasets/{d.get('id')}", 'source': 'huggingface'})
    return results

def search_datasets(query: str, limit: int=10) -> List[Dict]:
    return _hf_search(query, limit)
