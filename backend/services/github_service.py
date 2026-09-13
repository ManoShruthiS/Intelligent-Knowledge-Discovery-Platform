import logging
import os
from typing import Dict, List
import httpx
logger = logging.getLogger(__name__)
TIMEOUT = 12.0

def _headers() -> Dict[str, str]:
    h = {'Accept': 'application/vnd.github+json', 'User-Agent': 'KNO/1.0', 'X-GitHub-Api-Version': '2022-11-28'}
    token = os.getenv('GITHUB_TOKEN')
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h

def _github_search_repos(query: str, limit: int=10, sort: str='best-match') -> Dict:
    query = (query or '').strip()
    if not query:
        return {'results': [], 'available': True, 'rate_limit': None}
    url = 'https://api.github.com/search/repositories'
    params = {'q': query, 'per_page': max(1, min(30, limit))}
    sort_map = {'best-match': (None, None), 'stars': ('stars', 'desc'), 'updated': ('updated', 'desc'), 'forks': ('forks', 'desc')}
    sort_param, order_param = sort_map.get(sort, (None, None))
    if sort_param:
        params['sort'] = sort_param
        params['order'] = order_param
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers=_headers())
            if r.status_code == 403:
                return {'results': [], 'available': False, 'rate_limit': 'exceeded', 'error': 'GitHub API rate limit reached. Set GITHUB_TOKEN to raise the limit.'}
            if r.status_code != 200:
                logger.warning(f'GitHub returned {r.status_code}')
                return {'results': [], 'available': False, 'rate_limit': None, 'error': f'GitHub API status {r.status_code}'}
            data = r.json()
    except Exception as e:
        logger.warning(f'GitHub request failed: {e}')
        return {'results': [], 'available': False, 'rate_limit': None, 'error': str(e)}
    items = data.get('items', []) or []
    results: List[Dict] = []
    for r_item in items:
        results.append({'id': r_item.get('id'), 'full_name': r_item.get('full_name'), 'description': r_item.get('description'), 'html_url': r_item.get('html_url'), 'language': r_item.get('language'), 'stars': r_item.get('stargazers_count'), 'forks': r_item.get('forks_count'), 'open_issues': r_item.get('open_issues_count'), 'updated_at': r_item.get('updated_at'), 'topics': r_item.get('topics') or [], 'license': (r_item.get('license') or {}).get('spdx_id') if isinstance(r_item.get('license'), dict) else None, 'source': 'github'})
    return {'results': results, 'available': True, 'rate_limit': 'ok', 'total': data.get('total_count', len(results))}

def search_repositories(query: str, limit: int=10, sort: str='best-match') -> Dict:
    return _github_search_repos(query, limit, sort)
