import logging
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import httpx

# Ensure backend/.env is loaded regardless of the process working directory.
# (ai/config.py also calls load_dotenv(), but plain load_dotenv() only checks
# the CWD, so a server started from the repo root would miss backend/.env.)
try:
    from dotenv import load_dotenv
    _BACKEND_DIR = Path(__file__).resolve().parent.parent
    for _candidate in (_BACKEND_DIR / '.env', Path.cwd() / '.env', _BACKEND_DIR.parent / '.env'):
        if _candidate.is_file():
            load_dotenv(_candidate, override=False)
except Exception:
    pass

logger = logging.getLogger(__name__)
TIMEOUT = 10.0

MISSING_KEY_NOTE = 'YouTube API key not configured. Showing curated research learning resources.'


def is_youtube_configured() -> bool:
    return bool(os.getenv('YOUTUBE_API_KEY', '').strip())


def _youtube_search(query: str, limit: int = 12) -> Tuple[List[Dict], Optional[str]]:
    """Search YouTube. Returns (results, error).

    error is None on success (even with zero results), 'missing_key' when no
    API key is configured, or a short human-readable reason when the API call
    fails (invalid key, quota exceeded, network error, ...).
    """
    api_key = os.getenv('YOUTUBE_API_KEY', '').strip()
    if not api_key:
        return [], 'missing_key'
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {'part': 'snippet', 'q': f'{query} tutorial research lecture', 'type': 'video', 'maxResults': min(limit, 20), 'order': 'relevance', 'key': api_key}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params)
            if r.status_code != 200:
                reason = f'YouTube API returned HTTP {r.status_code}'
                try:
                    err_msg = (r.json().get('error') or {}).get('message', '')
                    if err_msg:
                        reason += f': {err_msg[:160]}'
                except Exception:
                    if r.text:
                        reason += f': {r.text[:160]}'
                logger.warning(reason)
                return [], reason
            data = r.json()
    except Exception as e:
        reason = f'YouTube request failed: {e}'
        logger.warning(reason)
        return [], reason
    results = []
    for item in data.get('items', []):
        snippet = item.get('snippet') or {}
        vid_id = (item.get('id') or {}).get('videoId')
        if not vid_id:
            continue
        results.append({'id': vid_id, 'title': snippet.get('title', ''), 'creator': snippet.get('channelTitle', ''), 'platform': 'YouTube', 'type': 'video', 'description': snippet.get('description', ''), 'published': snippet.get('publishedAt', '')[:10], 'thumbnail': (snippet.get('thumbnails') or {}).get('medium', {}).get('url'), 'url': f'https://www.youtube.com/watch?v={vid_id}', 'duration': None, 'source': 'youtube'})
    return results, None
CURATED = [{'id': 'curated-001', 'title': 'Attention Is All You Need — Paper Explained', 'creator': 'Yannic Kilcher', 'platform': 'YouTube', 'type': 'video', 'description': 'Deep dive into the Transformer paper by Vaswani et al. Covers self-attention, multi-head attention, positional encoding, encoder-decoder architecture.', 'published': '2020-06-21', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=iDulhoQ2pro', 'duration': '1h 5m', 'tags': ['transformer', 'attention', 'nlp', 'deep learning', 'paper explained']}, {'id': 'curated-002', 'title': 'Illustrated BERT, ELMo, and co.', 'creator': 'Jay Alammar', 'platform': 'Blog', 'type': 'article', 'description': 'Beautifully illustrated guide to modern NLP language models including BERT and ELMo, with detailed visual explanations.', 'published': '2018-12-03', 'thumbnail': None, 'url': 'https://jalammar.github.io/illustrated-bert/', 'duration': '30 min read', 'tags': ['bert', 'elmo', 'nlp', 'transformer', 'language model']}, {'id': 'curated-003', 'title': 'The Annotated Transformer', 'creator': 'Harvard NLP', 'platform': 'Blog', 'type': 'article', 'description': "Line-by-line PyTorch implementation of 'Attention Is All You Need' with detailed annotations and explanations.", 'published': '2022-04-05', 'thumbnail': None, 'url': 'https://nlp.seas.harvard.edu/annotated-transformer/', 'duration': '45 min read', 'tags': ['transformer', 'pytorch', 'implementation', 'nlp', 'attention']}, {'id': 'curated-004', 'title': 'A Survey of Large Language Models', 'creator': 'arXiv', 'platform': 'arXiv', 'type': 'article', 'description': 'Comprehensive survey covering LLM pre-training, instruction tuning, alignment, and applications. Essential reading for LLM researchers.', 'published': '2023-03-31', 'thumbnail': None, 'url': 'https://arxiv.org/abs/2303.18223', 'duration': 'Survey paper', 'tags': ['llm', 'large language models', 'survey', 'gpt', 'instruction tuning']}, {'id': 'curated-005', 'title': 'RAG — Retrieval-Augmented Generation Explained', 'creator': 'IBM Technology', 'platform': 'YouTube', 'type': 'video', 'description': 'Clear, accessible explanation of Retrieval-Augmented Generation — how it works, why it reduces hallucinations, and when to use it.', 'published': '2023-09-14', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=T-D1OfcDW1M', 'duration': '10 min', 'tags': ['rag', 'retrieval augmented generation', 'llm', 'vector database']}, {'id': 'curated-006', 'title': 'LangChain Full Course — Build LLM Apps', 'creator': 'freeCodeCamp', 'platform': 'YouTube', 'type': 'course', 'description': 'Full hands-on course building LLM-powered applications with LangChain, vector stores, agents, and RAG pipelines.', 'published': '2023-11-01', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=lG7Uxts9SXs', 'duration': '5h 30m', 'tags': ['langchain', 'llm', 'rag', 'vector store', 'agents', 'python']}, {'id': 'curated-007', 'title': 'Fast.ai Practical Deep Learning for Coders', 'creator': 'Jeremy Howard', 'platform': 'fast.ai', 'type': 'course', 'description': 'Top-down practical approach to deep learning. Covers CNNs, NLP, diffusion models, tabular data. Completely free with notebooks.', 'published': '2023-01-01', 'thumbnail': None, 'url': 'https://course.fast.ai/', 'duration': '9 lessons', 'tags': ['deep learning', 'machine learning', 'fastai', 'pytorch', 'practical']}, {'id': 'curated-008', 'title': 'Stanford CS224N: NLP with Deep Learning', 'creator': 'Stanford University', 'platform': 'YouTube', 'type': 'course', 'description': "Stanford's graduate NLP course. Covers word vectors, RNNs, transformers, BERT, question answering, and neural machine translation.", 'published': '2023-01-09', 'thumbnail': None, 'url': 'https://www.youtube.com/playlist?list=PLoROMvodv4rMFqRtEuo6SGjY4XbRIVx76', 'duration': '20 lectures', 'tags': ['nlp', 'deep learning', 'stanford', 'bert', 'transformer', 'lecture']}, {'id': 'curated-009', 'title': "Andrej Karpathy — Let's build GPT from scratch", 'creator': 'Andrej Karpathy', 'platform': 'YouTube', 'type': 'video', 'description': 'Build a character-level GPT from scratch in code. Covers attention, transformers, token generation. Ideal for deep understanding.', 'published': '2023-01-17', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=kCc8FmEb1nY', 'duration': '1h 56m', 'tags': ['gpt', 'transformer', 'implementation', 'pytorch', 'language model']}, {'id': 'curated-010', 'title': 'Stanford CS231n: Deep Learning for Computer Vision', 'creator': 'Stanford University', 'platform': 'YouTube', 'type': 'course', 'description': 'Classic Stanford computer vision course. CNNs, object detection, segmentation, GANs, and modern vision architectures.', 'published': '2017-04-01', 'thumbnail': None, 'url': 'https://www.youtube.com/playlist?list=PLC1qU-LWwrF64f4QKQT-Vg5Wr4qEE1Zxk', 'duration': '16 lectures', 'tags': ['computer vision', 'cnn', 'deep learning', 'stanford', 'object detection']}, {'id': 'curated-011', 'title': 'How to Read a Research Paper', 'creator': 'Andrew Ng', 'platform': 'YouTube', 'type': 'video', 'description': 'Andrew Ng explains his strategy for reading research papers effectively — the three-pass approach and how to build literature understanding.', 'published': '2018-08-01', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=733m6qBH-jI', 'duration': '10 min', 'tags': ['research', 'literature review', 'study skills', 'academic', 'reading']}, {'id': 'curated-012', 'title': 'Machine Learning with Python Full Course', 'creator': 'freeCodeCamp', 'platform': 'YouTube', 'type': 'course', 'description': 'Comprehensive machine learning course using scikit-learn, TensorFlow, and Keras. Covers regression, classification, clustering, deep learning.', 'published': '2022-06-15', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=i_LwzRVP7bg', 'duration': '6h 25m', 'tags': ['machine learning', 'python', 'scikit-learn', 'tensorflow', 'deep learning']}, {'id': 'curated-013', 'title': 'AI Agents — Full Course', 'creator': 'DeepLearning.AI', 'platform': 'DeepLearning.AI', 'type': 'course', 'description': 'Building AI agents with tool use, planning, and multi-agent collaboration. Covers ReAct, function calling, and agentic workflows.', 'published': '2024-01-01', 'thumbnail': None, 'url': 'https://www.deeplearning.ai/short-courses/', 'duration': 'Short courses', 'tags': ['agents', 'llm', 'tool use', 'planning', 'multi-agent', 'autonomous']}, {'id': 'curated-014', 'title': 'Vector Databases Explained', 'creator': 'Fireship', 'platform': 'YouTube', 'type': 'video', 'description': 'Fast-paced explanation of vector embeddings, similarity search, FAISS, Chroma, Pinecone — core building blocks of modern AI apps.', 'published': '2023-07-12', 'thumbnail': None, 'url': 'https://www.youtube.com/watch?v=klTvEwg3oJ4', 'duration': '10 min', 'tags': ['vector database', 'embeddings', 'faiss', 'similarity search', 'rag']}, {'id': 'curated-015', 'title': 'Hugging Face Course — NLP with Transformers', 'creator': 'Hugging Face', 'platform': 'Hugging Face', 'type': 'course', 'description': 'Official Hugging Face course covering the Transformers library, fine-tuning BERT, GPT-2, T5 and more. Free and practical.', 'published': '2022-02-01', 'thumbnail': None, 'url': 'https://huggingface.co/course/chapter1', 'duration': '8 chapters', 'tags': ['hugging face', 'transformers', 'bert', 'fine-tuning', 'nlp', 'python']}]

def _score_resource(r: Dict, query_words: List[str]) -> float:
    if not query_words:
        return 1.0
    text = ((r.get('title') or '') + ' ' + (r.get('description') or '') + ' ' + ' '.join(r.get('tags') or [])).lower()
    hits = sum((1 for w in query_words if w in text))
    return hits / len(query_words)

def _stop_words():
    return {'a', 'an', 'the', 'of', 'in', 'on', 'for', 'to', 'with', 'by', 'from', 'is', 'are', 'and', 'or', 'not', 'this', 'that', 'it', 'its', 'be', 'as', 'at', 'we', 'i', 'my', 'how', 'what', 'why', 'when', 'where', 'which', 'who'}

def search_learning(query: str, limit: int=12) -> Dict:
    query = (query or '').strip()
    query_lower = query.lower()
    stop = _stop_words()
    query_words = [w for w in re.split('[^a-z0-9]+', query_lower) if w and w not in stop and (len(w) > 2)]
    yt_results, yt_error = _youtube_search(query, limit)
    if yt_results:
        return {'results': yt_results[:limit], 'query': query, 'source': 'youtube', 'total': len(yt_results)}
    if yt_error is None:
        # Key is configured and the API call succeeded, but YouTube returned
        # zero videos — report that honestly instead of implying a key problem.
        return {'results': [], 'query': query, 'source': 'youtube', 'total': 0, 'note': 'No YouTube videos found for this query.'}
    scored = [(r, _score_resource(r, query_words)) for r in CURATED]
    if query_words:
        relevant = [(r, s) for r, s in scored if s > 0]
        if not relevant:
            relevant = scored
        relevant.sort(key=lambda x: -x[1])
        results = [r for r, _ in relevant[:limit]]
    else:
        results = [r for r, _ in scored[:limit]]
    if yt_error == 'missing_key':
        note = MISSING_KEY_NOTE
    else:
        note = f'YouTube search unavailable ({yt_error}). Showing curated research learning resources.'
    return {'results': results, 'query': query, 'source': 'curated', 'total': len(results), 'note': note}
