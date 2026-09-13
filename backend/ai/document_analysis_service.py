import collections
import hashlib
import json
import logging
import math
import re
import string
from typing import Dict, List, Optional, Tuple, Callable
import database.database as db
try:
    from ai.llm_service import llm_service, LLMNotConfiguredError
except Exception:
    llm_service = None

    class LLMNotConfiguredError(Exception):
        pass
logger = logging.getLogger(__name__)

class LLMUnavailableError(Exception):
    pass
MAX_CHUNKS_IN_CONTEXT = 40
MAX_CONTEXT_CHARS = 60000
MAX_SUB_RETRIEVAL_DEPTH = 3
ASPECT_TOP_K = 4

def _clean_output_text(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    text = re.sub('\\s*\\n\\s*', ' ', text)
    text = re.sub('  +', ' ', text)
    text = re.sub('^\\d+(?:\\.\\d+)*\\s+', '', text)
    section_headings = ('introduction', 'background', 'method', 'methodology', 'approach', 'results', 'analysis', 'discussion', 'conclusion', 'conclusions', 'abstract', 'related work', 'summary', 'findings', 'experiments')
    text_lower = text.lower()
    for heading in section_headings:
        if text_lower.startswith(heading + ' '):
            text = text[len(heading):].lstrip()
            text_lower = text.lower()
            break
    for heading in section_headings:
        if text_lower.endswith(' ' + heading):
            text = text[:-(len(heading) + 1)].rstrip()
            text_lower = text.lower()
            break
    return text.strip()
RESEARCH_PAPER_HINTS = ('abstract', 'introduction', 'methodology', 'experiments', 'results', 'discussion', 'conclusion', 'references', 'we propose', 'we present', 'in this paper', 'this work', 'literature review', 'datasets', 'benchmark', 'training', 'evaluation', 'baseline', 'state-of-the-art', 'neural network', 'deep learning', 'machine learning')
TECHNICAL_DOC_HINTS = ('api', 'endpoint', 'request', 'response', 'class', 'function', 'method', 'parameter', 'returns', 'throws', 'example', 'usage', 'install', 'configuration', 'setup', 'deploy', 'tutorial', 'documentation', 'reference', 'guide', 'specification')

def _load_document_or_404(document_id: str) -> Dict:
    doc = db.get_document_by_id(document_id)
    if not doc:
        raise ValueError(f'Document {document_id} not found.')
    return doc

def _get_chunks_sorted(document_id: str) -> List[Dict]:
    chunks = db.get_chunks_for_document(document_id)
    chunks.sort(key=lambda c: c.get('chunk_index', 0))
    return chunks

def _stratified_sample(chunks: List[Dict], max_n: int) -> List[Dict]:
    if len(chunks) <= max_n:
        return chunks
    third = max_n // 3
    head = chunks[:third]
    mid_start = (len(chunks) - third) // 2
    middle = chunks[mid_start:mid_start + third]
    tail = chunks[-third:]
    seen, out = (set(), [])
    for c in head + middle + tail:
        if c['id'] in seen:
            continue
        seen.add(c['id'])
        out.append(c)
    return out

def _format_chunks_for_prompt(chunks: List[Dict]) -> str:
    blocks = []
    total_chars = 0
    for i, chunk in enumerate(chunks, 1):
        page = chunk.get('page_number')
        page_info = f' (page {page})' if page is not None else ''
        text = (chunk.get('text') or '').strip()
        if not text:
            continue
        block = f'[CHUNK {i}{page_info}]\n{text}'
        if total_chars + len(block) > MAX_CONTEXT_CHARS:
            remaining = max(0, MAX_CONTEXT_CHARS - total_chars)
            if remaining > 200:
                block = block[:remaining] + '\n...[truncated]'
                blocks.append(block)
                total_chars += len(block)
            break
        blocks.append(block)
        total_chars += len(block)
    return '\n\n'.join(blocks)

def _confidence_label(sources: List[Dict]) -> str:
    if not sources:
        return 'unverified'
    if len(sources) >= 3:
        return 'grounded'
    return 'partial'

def _detect_document_type(doc: Dict) -> str:
    if hasattr(doc, 'keys'):
        doc = dict(doc)
    text = (doc.get('extracted_text') or '')[:6000].lower()
    file_type = (doc.get('file_type') or '').lower()
    if not text:
        return 'general'
    rp_hits = sum((1 for kw in RESEARCH_PAPER_HINTS if kw in text))
    tech_hits = sum((1 for kw in TECHNICAL_DOC_HINTS if kw in text))
    if file_type in {'pdf'} and rp_hits >= 4:
        return 'research_paper'
    if file_type in {'markdown', 'md'} and rp_hits >= 4:
        return 'research_paper'
    if tech_hits >= 4 and tech_hits > rp_hits:
        return 'technical_document'
    if rp_hits >= 3 and rp_hits > tech_hits:
        return 'research_paper'
    if tech_hits >= 3 and tech_hits > rp_hits:
        return 'technical_document'
    return 'general'

def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _parse_json_safely(raw: str) -> Dict:
    text = (raw or '').strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {'_raw': data}
    except Exception as e:
        logger.warning(f'JSON parse failed: {e}; head: {raw[:200]}')
        return {}

def _empty_paper_summary() -> Dict:
    return {'title': None, 'authors': None, 'year': None, 'venue': None, 'research_problem': None, 'research_objective': None, 'background': None, 'proposed_approach': None, 'methodology': None, 'dataset': None, 'models_algorithms': None, 'experimental_setup': None, 'evaluation_metrics': None, 'main_results': None, 'key_findings': None, 'main_contribution': None, 'limitations': None, 'future_work': None, 'conclusion': None, 'keywords': []}

def _empty_general_summary() -> Dict:
    return {'title': None, 'summary': None, 'key_points': [], 'topics': [], 'document_structure': []}

def _empty_paper_insights() -> Dict:
    return {'key_concepts': [], 'important_entities': [], 'methods': [], 'algorithms': [], 'models': [], 'datasets': [], 'metrics': [], 'findings': [], 'contributions': [], 'limitations': [], 'assumptions': [], 'future_directions': [], 'relationships': [], 'document_structure': []}

def _empty_general_insights() -> Dict:
    return {'key_concepts': [], 'important_entities': [], 'methods': [], 'key_points': [], 'topics': [], 'action_items': [], 'document_structure': []}
_BASE_RULES = 'You are ORBOT in DOCUMENT ANALYSIS mode.\n\nThe user has uploaded a document. You will read the chunks provided below\nand produce a grounded analysis.\n\nNON-NEGOTIABLE RULES:\n1. Use ONLY information that appears in the supplied chunks.\n2. Do NOT invent citations, paper titles, authors, DOI numbers, URLs,\n   page numbers, statistics, experimental results, dataset names, or\n   methodology details.\n3. If the document does not contain information needed to answer a\n   section of the analysis, explicitly set that field to the literal\n   string "Not stated in the document." (and only that string).\n4. Quote phrases verbatim only when useful; otherwise paraphrase.\n5. Distinguish what the document STATES (FACT) from what you are\n   INTERPRETING from it (INFERENCE). Prefer FACT.\n6. Never present an inference as if it were a stated fact.\n7. Do NOT add information that is common knowledge but not in the\n   supplied chunks.\n8. Do NOT begin with pleasantries or meta-commentary. Jump straight into\n   the requested output.\n\nEVIDENCE:\n- For each meaningful claim, you may cite the source chunk(s) using\n  the format: {"chunk_indices": [1, 2], "page": 3, "snippet": "<≤25-word quote>"}.\n- "chunk_indices" are 1-based and refer to the numbered [CHUNK n] labels\n  in the context.\n- "page" is the page number from the chunks if known, otherwise null.\n- "snippet" must be a VERBATIM excerpt of ≤25 words from the cited chunks.\n  If you cannot quote verbatim, omit the snippet field.\n- Do NOT cite a chunk you did not actually read.\n- If a field is supported by no chunk, omit its evidence.\n'
_PAPER_SUMMARY_PROMPT = '{base}\n\nTASK: Produce a structured research-paper summary for the supplied chunks.\n\nOUTPUT FORMAT (strict JSON, no markdown wrapper):\n\n{{\n  "title": <string|null>,\n  "authors": <string|null>,                    // comma-separated list, or null\n  "year": <integer|null>,\n  "venue": <string|null>,                      // journal/conference name\n  "research_problem": <string|None>,           // "Not stated in the document." if absent\n  "research_objective": <string|null>,\n  "background": <string|null>,\n  "proposed_approach": <string|null>,\n  "methodology": <string|null>,\n  "dataset": <string|null>,\n  "models_algorithms": <string|null>,\n  "experimental_setup": <string|null>,\n  "evaluation_metrics": <string|null>,\n  "main_results": <string|null>,\n  "key_findings": <string|null>,\n  "main_contribution": <string|null>,\n  "limitations": <string|null>,\n  "future_work": <string|null>,\n  "conclusion": <string|null>,\n  "keywords": [<string>, ...],                 // 5-12 specific terms\n  "evidence": [                                 // optional top-level evidence for headline claims\n    {{\n      "field": "<one of: title|research_problem|methodology|key_findings|limitations|...>",\n      "chunk_indices": [3, 7],\n      "page": 4,\n      "snippet": "<≤25 word verbatim quote>"\n    }}\n  ]\n}}\n\nCONSTRAINTS:\n- Strings must be concise: 1–3 sentences each. No lists inside strings.\n- If a field is absent, use exactly: "Not stated in the document."\n- Never put placeholder values like "N/A", "—", or "" in place of the\n  literal "Not stated in the document." string.\n- The "evidence" array is OPTIONAL but useful for the most important\n  claims (e.g. main_contribution, key_findings, limitations). Keep it to\n  3–6 entries. Do NOT generate evidence for every field.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END DOCUMENT CHUNKS ===\n\nBegin now.\n'
_TECHNICAL_SUMMARY_PROMPT = '{base}\n\nTASK: Produce a structured technical-document summary for the supplied chunks.\n\nOUTPUT FORMAT (strict JSON, no markdown wrapper):\n\n{{\n  "title": <string|null>,\n  "kind": <"library"|"tutorial"|"specification"|"guide"|"report"|null>,\n  "purpose": <string|null>,\n  "audience": <string|null>,\n  "key_concepts": [<string>, ...],\n  "main_sections": [                           // 3-8 high-level sections\n    {{"heading": <string>, "summary": <string>, "evidence": {{"chunk_indices": [1, 2], "page": 3, "snippet": "<≤25 word quote>"}}}}\n  ],\n  "api_or_commands": [<string>, ...],          // if any\n  "requirements": [<string>, ...],\n  "examples": [<string>, ...]\n}}\n\nCONSTRAINTS:\n- "Not stated in the document." for any missing single-value string.\n- Only include "main_sections" that the document actually contains.\n- "examples" should reference the document\'s example code or output, not invented ones.\n- Do not fabricate API endpoints or commands.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END DOCUMENT CHUNKS ===\n\nBegin now.\n'
_GENERAL_SUMMARY_PROMPT = '{base}\n\nTASK: Produce a structured general-document summary for the supplied chunks.\n\nOUTPUT FORMAT (strict JSON, no markdown wrapper):\n\n{{\n  "title": <string|null>,\n  "summary": <string|null>,                   // 1-3 sentences, "Not stated..." if absent\n  "key_points": [<string>, ...],              // 3-8 bullets\n  "topics": [<string>, ...],                  // 5-10 keywords\n  "evidence": [\n    {{\n      "field": "summary|key_points|topics",\n      "chunk_indices": [3],\n      "page": 2,\n      "snippet": "<≤25 word quote>"\n    }}\n  ]\n}}\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END DOCUMENT CHUNKS ===\n\nBegin now.\n'
_PAPER_INSIGHTS_PROMPT = '{base}\n\nTASK: Extract a structured set of insights from this research-paper document.\n\nOUTPUT FORMAT (strict JSON, no markdown wrapper):\n\n{{\n  "key_concepts": [\n    {{"concept": "<name>", "why_it_matters": "<1 sentence grounded in the document>", "evidence": {{"chunk_indices": [1], "page": 3, "snippet": "<≤25 word quote>"}}}}\n  ],\n  "important_entities": [\n    {{"entity": "<name>", "kind": "<person|org|method|dataset|metric|model|tool>", "role": "<short role>", "evidence": {{"chunk_indices": [2], "page": 5, "snippet": "<≤25 word quote>"}}}}\n  ],\n  "methods":    [{{"name": "<name>", "description": "<short>", "evidence": {{"chunk_indices": [3], "page": 4, "snippet": "<≤25 word quote>"}}}}],\n  "algorithms": [{{"name": "<name>", "description": "<short>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "models":     [{{"name": "<name>", "purpose": "<short>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "datasets":   [{{"name": "<name>", "role": "<short>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "metrics":    [{{"metric": "<name>", "value": "<value>", "context": "<short>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "findings":   [{{"finding": "<single sentence grounded in the document>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "contributions": [{{"contribution": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "limitations": [{{"limitation": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "assumptions": [{{"assumption": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "future_directions": [{{"direction": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "relationships": [\n    {{\n      "from": "<concept A>", "to": "<concept B>",\n      "kind": "<uses|improves|extends|contrasts-with|enables>",\n      "description": "<short>",\n      "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}\n    }}\n  ]\n}}\n\nCONSTRAINTS:\n- Every array MUST be present. Use [] when there is nothing to list.\n- Each item string is concise: one sentence per bullet maximum.\n- For each item, evidence is OPTIONAL but recommended for at least\n  the first 1-3 items in each array when supporting chunks exist.\n- For sections where evidence is unclear, omit the evidence object\n  (set chunk_indices to []).\n- Do NOT invent numbers, dataset names, or model names.\n- Return ONLY valid JSON. Do NOT wrap it in ``` fences. Do NOT add any\n  prose before or after the JSON.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END DOCUMENT CHUNKS ===\n'
_GENERAL_INSIGHTS_PROMPT = '{base}\n\nTASK: Extract a structured set of insights from this general document.\n\nOUTPUT FORMAT (strict JSON, no markdown wrapper):\n\n{{\n  "key_concepts":      [{{"concept": "<name>", "why_it_matters": "<1 sentence>", "evidence": {{"chunk_indices": [1], "page": 3, "snippet": "<≤25 word quote>"}}}}],\n  "important_entities": [{{"entity": "<name>", "kind": "<person|org|tool|system>", "role": "<short>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "key_points":        [{{"point": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}],\n  "topics":            [<string>, ...],\n  "action_items":      [{{"action": "<single sentence>", "evidence": {{"chunk_indices": [], "page": null, "snippet": ""}}}}]\n}}\n\nCONSTRAINTS:\n- Each item string is concise: one sentence per bullet maximum.\n- evidence is OPTIONAL but encouraged for the first 1-3 items in each array.\n- Do NOT invent facts not in the chunks.\n- Return ONLY valid JSON. Do NOT wrap it in ``` fences. Do NOT add any prose before or after the JSON.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END DOCUMENT CHUNKS ===\n'
_STOP_WORDS = frozenset('a an the and or but in on at to of for with by from is are was were be been being have has had do does did will would could should may might must shall this that these those it its we our they their you your he she his her i me him us them what which who when where why how all any both each few more most other some such no not only same so than too very just can about into through during before after above below up down out off over under again further then once here there if because as until while also however while although since though whereas whether either neither nor yet so paper study result method conference proceedings work approach use used using based show demonstrate propose present introduce establish one two three four five six seven eight nine ten new first second third last next previous current following also moreover furthermore addition finally however therefore thus hence accordingly consequently similarly likewise specifically particularly especially notably importantly generally typically usually normally frequently often relatively approximately roughly essentially basically simultaneously respectively independently collectively respectively given provided assume assume'.split())
_GENERIC_CONCEPT_WORDS = frozenset('paper study result method conference proceedings approach work use based show demonstrate propose present introduce establish authors given paper section chapter table figure figure shows based using following provide several different well known first second third however also moreover furthermore addition conclusion finally summary introduction background related previous existing prior recent recent years respectively considered regard respect terms although though whereas whether involved involving particular particular case cases considered including included include various various aspects various methods performance evaluation experimental experimental results obtained comparison compared state art given provided assume large number set part used order ensure allow enable high low many much each every both between among within across along around behind below beneath beside beyond detail details level overall total sum average table figure show presents lists describes provides discusses explains indicates suggests notes mentions refers points states reports notes observes given known common well-known widely used consists comprises contains includes comprises form defined represents corresponds denotes process process step steps phase type types kind kinds category categories value values property properties feature features component components element elements part parts case cases example examples instance instances section sections chapter chapters part parts text string number word sentence paragraph time place location position direction function role purpose goal objective problem solution issue issue issues model approach method technique data information knowledge system process framework table figure equation formula result findings observation observations given paper work section following present discuss describe introduce provide establish show demonstrate indicate propose develop design existing previous subsequent various several multiple different similar respective corresponding particular specific general specific special important significant relevant potential possible necessary sufficient appropriate suitable appropriate suitable equivalent well known commonly used widely used extensively used typically generally generally considered approximately roughly essentially primarily mainly chiefly relatively comparatively particularly especially notably significantly substantially considerably relatively approximately roughly respectively independently simultaneously concurrently consequently subsequently alternatively conversely specifically particularly essentially fundamentally essentially basically essentially primarily essentially mainly essentially chiefly essentially predominantly essentially mostly essentially largely essentially primarily essentially mainly essentially chiefly essentially predominantly essentially mostly essentially largely'.split())
_METRIC_PATTERNS = re.compile('\\b(?:accuracy|precision|recall|f1|auc|roc|bleu|rouge|perplexity|loss|error rate|top-?\\d|mrr|ndcg|mse|mae|rmse|psnr|ssim|flops|params|throughput|latency|speedup|gain|improvement|exact match|em score|f1 score)\\b', re.IGNORECASE)
_VALUE_PATTERNS = re.compile('(\\d+\\.?\\d*%|\\d+\\.\\d+|\\d{2,}(?:\\.\\d+)?)(?:\\s*(?:pp|points?|percent(?:age)?))?')
_SECTION_HEADINGS = re.compile('^(?:\\d+\\.?\\s*)?(abstract|introduction|related work|background|methodology|method|approach|architecture|model|experiments?|evaluation|results?|discussion|conclusions?|future work|limitations?|acknowledgements?|references|problem statement|research problem|motivation|prior work|previous work|existing work|proposed method|proposed approach|proposed model|proposed framework|training|inference|deployment|implementation|analysis|findings|summary|overview|appendix|supplementary|glossary|definitions|problem definition|task definition|formulation|data|dataset|datasets|corpus|benchmarks?|baselines?|comparison|comparative|ablation|analysis|discussion|conclusion|concluding|final remarks|authors?|contributors?|affiliations?|keywords?|categories?|subject descriptors?)\\s*$', re.IGNORECASE | re.MULTILINE)
_ENTITY_PATTERNS = {'model': re.compile('\\b(BERT|GPT(?:-?\\d+)?|T5|RoBERTa|ALBERT|XLNet|LLaMA(?:-?\\d+)?|Mistral|Gemma|Claude|Gemini|PaLM|ResNet(?:-?\\d+)?|VGG(?:-?\\d+)?|ViT|CLIP|DALL-E|Stable Diffusion|Transformer|LSTM|CNN|GAN|VAE|Word2Vec|GloVe|FastText|SBERT|DPR|ColBERT|BART|BLOOM|Falcon|ELECTRA|DeBERTa|SpanBERT|DistilBERT|Reformer|Perceiver|BEiT|Swin|MAE|DINO|SAM|Whisper|ChatGPT|GPT-[1234]|GPT-4o|RAG-Sequence|RAG-Token|Encoder-Decoder|Seq2Seq|Sequence-to-Sequence|Cross-Encoder|Bi-Encoder|Retrieval-Augmented|Fusion-in-Decoder|Prefix LM|Decoder-Only|Encoder-Only)\\b', re.IGNORECASE), 'dataset': re.compile('\\b(ImageNet|COCO|SQuAD|GLUE|SuperGLUE|MNIST|CIFAR-?\\d+|WikiText|CommonCrawl|C4|WMT\\d{2}|MS MARCO|TriviaQA|Natural Questions|HotpotQA|ARC Challenge|HellaSwag|MMLU|BIG-Bench|OpenWebText|The Pile|LAION|BookCorpus|Wikipedia|LibriSpeech|MultiRC|ReCoRD|BoolQ|PIQA|WinoGrande|OpenBookQA|FEVER|ANLI|SNLI|MultiNLI|PAWS|QQP|SST-?2|CoLA|MRPC|QNLI|RTE|STSB|IMDB|AG News|20 Newsgroups|Reuters|PubMed|arXiv|Semantic Scholar|WebQuestions|ComplexWebQuestions|NewsQA|NarrativeQA|QuAC|CoQA|DROP|TyDi QA|XOR QA|MLQA|XQuAD|SIB-200|MultiWOZ|CoNLL-?2003|OntoNotes|ACE 2005|TACRED)\\b', re.IGNORECASE), 'framework': re.compile('\\b(PyTorch|TensorFlow|JAX|Keras|HuggingFace|Transformers|scikit-learn|sklearn|NumPy|Pandas|SciPy|spaCy|NLTK|FAISS|Faiss|Annoy|ScaNN|Elasticsearch|Solr|Weaviate|Pinecone|Milvus|Chroma|Qdrant|LanceDB|Haystack|LangChain|LlamaIndex|Ray|Dask|Spark|Docker|Kubernetes|K8s|Flask|FastAPI|Django|React|Vue|Angular|Node\\.js|Express|Spring|PostgreSQL|MySQL|MongoDB|Redis|AWS|Azure|GCP)\\b', re.IGNORECASE), 'metric': re.compile('\\b(BLEU|ROUGE-?[LN12]?|METEOR|BERTScore|Exact Match|F1 Score|F1\\b|Accuracy|Precision|Recall|AUC-?ROC|MRR|NDCG|Perplexity|Top-?\\d+ Accuracy|MAP|Recall@K|Hit Rate|BEER|COMET|ChrF|TER|Word Error Rate|WER|CER|Cohen kappa|Fleiss kappa|p-value|Confidence Interval|Standard Deviation|Standard Error|Mean Squared Error|Root Mean Squared|Mean Absolute Error|R-squared|Information Gain|Chi-squared|Gini Index|Mutual Information|Silhouette Score|Rand Index|Jaccard Similarity|Cosine Similarity|Euclidean Distance|Edit Distance|Levenshtein|Jaccard)\\b', re.IGNORECASE)}

class LocalAnalysisEngine:

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall('[a-zA-Z]{3,}', text.lower())
        return [t for t in tokens if t not in _STOP_WORDS]

    def _tf(self, tokens: List[str]) -> Dict[str, float]:
        if not tokens:
            return {}
        counter = collections.Counter(tokens)
        max_count = max(counter.values())
        return {w: c / max_count for w, c in counter.items()}

    def _idf(self, docs: List[List[str]]) -> Dict[str, float]:
        N = len(docs) or 1
        df: Dict[str, int] = collections.defaultdict(int)
        for doc_tokens in docs:
            for w in set(doc_tokens):
                df[w] += 1
        return {w: math.log((N + 1) / (cnt + 1)) + 1 for w, cnt in df.items()}

    def _tfidf_keywords(self, texts: List[str], top_k: int=12) -> List[str]:
        all_tokens = [self._tokenize(t) for t in texts]
        idf = self._idf(all_tokens)
        combined = [t for sublist in all_tokens for t in sublist]
        tf = self._tf(combined)
        scores = {w: tf.get(w, 0) * idf.get(w, 0) for w in set(combined)}
        for text in texts:
            for match in re.finditer('\\b[A-Z][a-z]{2,}(?:\\s[A-Z][a-z]{2,})*\\b', text):
                word = match.group().lower()
                if word in scores:
                    scores[word] *= 1.4
        phrase_scores: Dict[str, float] = {}
        phrase_original: Dict[str, str] = {}
        for text in texts:
            for match in re.finditer('\\b([A-Z][a-zA-Z]+(?:[^\\S\\n]+[A-Z][a-zA-Z]+)+)\\b', text):
                phrase = match.group().strip()
                phrase = re.sub('\\s+', ' ', phrase)
                phrase_lower = phrase.lower()
                phrase_words = phrase_lower.split()
                if len(phrase_words) >= 2 and all((w in scores for w in phrase_words)):
                    phrase_scores[phrase_lower] = sum((scores[w] for w in phrase_words)) * 1.8
                    phrase_original[phrase_lower] = phrase
            for match in re.finditer('\\b([A-Za-z]+(?:-[A-Za-z]+){1,3})\\b', text):
                term = match.group().strip()
                if len(term) > 5:
                    phrase_scores[term.lower()] = phrase_scores.get(term.lower(), 0) + 2.0
                    phrase_original[term.lower()] = term
        technical_phrases = {'retrieval augmented generation': 3.0, 'retrieval-augmented generation': 3.0, 'dense passage retrieval': 3.0, 'neural machine translation': 2.5, 'natural language processing': 2.0, 'natural language understanding': 2.0, 'natural language generation': 2.0, 'machine reading comprehension': 2.5, 'question answering': 2.0, 'text classification': 2.0, 'sentiment analysis': 2.0, 'named entity recognition': 2.5, 'relation extraction': 2.5, 'information extraction': 2.0, 'information retrieval': 2.5, 'document ranking': 2.0, 'passage ranking': 2.0, 'language model': 2.0, 'pre-trained model': 2.0, 'pretrained model': 2.0, 'fine-tuning': 2.0, 'fine tuning': 2.0, 'transfer learning': 2.0, 'few-shot learning': 2.0, 'zero-shot learning': 2.0, 'self-supervised learning': 2.5, 'contrastive learning': 2.5, 'knowledge distillation': 2.5, 'model compression': 2.0, 'attention mechanism': 2.0, 'self-attention': 2.0, 'multi-head attention': 2.5, 'encoder-decoder': 2.0, 'seq2seq': 2.0, 'sequence-to-sequence': 2.0, 'beam search': 2.0, 'greedy decoding': 2.0, 'word embeddings': 2.0, 'contextual embeddings': 2.5, 'contextualized representations': 2.5, 'context window': 2.0, 'tokenization': 1.5, 'subword tokenization': 2.5, 'byte pair encoding': 2.5, 'word piece': 2.0, 'sentencepiece': 2.0, 'batch processing': 1.5, 'data augmentation': 2.0, 'cross-validation': 2.0, 'ablation study': 2.5, 'baseline comparison': 2.0, 'state of the art': 2.0, 'state-of-the-art': 2.0, 'performance improvement': 1.5, 'statistical significance': 2.0}
        full_text_combined = ' '.join(texts).lower()
        for phrase, boost in technical_phrases.items():
            if phrase in full_text_combined:
                count = full_text_combined.count(phrase)
                phrase_key = phrase
                phrase_scores[phrase_key] = phrase_scores.get(phrase_key, 0) + boost * min(count, 5)
                phrase_original[phrase_key] = phrase.title() if phrase == phrase.lower() else phrase
        all_scores = {**scores, **phrase_scores}
        filtered = {w: s for w, s in all_scores.items() if w not in _GENERIC_CONCEPT_WORDS and w not in _STOP_WORDS}
        sorted_words = sorted(filtered, key=lambda w: filtered[w], reverse=True)
        seen, out = (set(), [])
        for w in sorted_words:
            normalized = w.lower().strip()
            if normalized not in seen and len(out) < top_k:
                seen.add(normalized)
                if normalized in phrase_original:
                    out.append(phrase_original[normalized])
                elif len(w.split()) == 1:
                    out.append(w.title())
                else:
                    out.append(w)
        return out

    def _score_sentences(self, sentences: List[str], keywords: List[str], section_hints: Optional[Dict[str, str]]=None) -> List[Tuple[float, str]]:
        kw_set = {k.lower() for k in keywords}
        n = len(sentences)
        scored = []
        for i, sent in enumerate(sentences):
            if len(sent.split()) < 5:
                continue
            tokens = self._tokenize(sent)
            kw_hits = sum((1 for t in tokens if t in kw_set))
            density = kw_hits / (len(tokens) + 1)
            pos_bonus = 0.0
            if n > 0:
                rel = i / n
                if rel < 0.2:
                    pos_bonus = 0.3
                elif rel > 0.85:
                    pos_bonus = 0.2
                elif 0.2 <= rel < 0.5:
                    pos_bonus = 0.1
            wc = len(sent.split())
            length_score = 1.0 if 15 <= wc <= 40 else 0.7 if wc >= 10 else 0.4
            contrib_bonus = 0.0
            sent_lower = sent.lower()
            contrib_markers = ('show', 'demonstrate', 'achieve', 'outperform', 'improve', 'propose', 'present', 'introduce', 'establish', 'find', 'reveal', 'validate', 'confirm', 'prove', 'yield', 'surpass', 'exceed', 'reduce', 'increase', 'enable', 'result', 'suggest', 'novel', 'significant', 'effective', 'efficient', 'robust', 'scalable', 'addresses', 'tackles', 'solves', 'overcomes', 'comprehensive', 'rigorous')
            if any((m in sent_lower for m in contrib_markers)):
                contrib_bonus = 0.15
            penalty = 0.0
            generic_prefixes = ('in this ', 'this paper ', 'in recent ', 'recently ', 'it is well ', 'it has been ', 'it is known ', 'in general ', 'generally ', 'typically ', 'usually ', 'therefore ', 'however ', 'moreover ', 'furthermore ', 'additionally ', 'consequently ', 'accordingly ', 'specifically ', 'particularly ', 'especially ', 'given the ', 'given a ', 'given that ')
            if any((sent_lower.startswith(p) for p in generic_prefixes)):
                penalty = 0.2
            score = (density + pos_bonus + contrib_bonus - penalty) * length_score
            scored.append((score, sent))
        return scored

    def _extract_sentences(self, text: str) -> List[str]:
        raw = re.split('(?<=[.!?])\\s+', text)
        cleaned = []
        for s in raw:
            s = s.strip()
            if len(s) > 20:
                cleaned.append(s)
        return cleaned

    def _extractive_summary(self, chunks: List[Dict], doc: Dict=None, num_sentences: int=6, doc_type: str='general') -> str:
        texts = [c.get('text', '') for c in chunks] if chunks else []
        if not texts and doc and doc.get('extracted_text'):
            texts = [doc.get('extracted_text')]
        if not texts:
            return 'No text content available for summary generation.'
        full_text = ' '.join(texts)
        sentences = self._extract_sentences(full_text)
        if not sentences:
            return full_text[:500]
        keywords = self._tfidf_keywords(texts, top_k=20)
        scored = self._score_sentences(sentences, keywords)
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = []
        seen_positions = set()
        for score, sent in scored:
            if len(selected) >= num_sentences:
                break
            orig_idx = sentences.index(sent) if sent in sentences else -1
            bucket = orig_idx // max(1, len(sentences) // 5)
            if bucket not in seen_positions or len(selected) < num_sentences // 2:
                selected.append(sent)
                seen_positions.add(bucket)
        original_order = {s: i for i, s in enumerate(sentences)}
        selected.sort(key=lambda s: original_order.get(s, 9999))
        return ' '.join(selected)

    def _detect_sections(self, chunks: List[Dict]) -> Dict[str, str]:
        sections: Dict[str, List[str]] = collections.defaultdict(list)
        current_section = 'body'
        if chunks:
            for chunk in chunks:
                text = (chunk.get('text') or '').strip()
                if not text:
                    continue
                first_line = text.split('\n')[0].strip()
                match = _SECTION_HEADINGS.match(first_line)
                if match:
                    current_section = match.group(1).lower().replace(' ', '_')
                sections[current_section].append(text)
        return {k: ' '.join(v)[:800] for k, v in sections.items()}

    def _detect_sections_from_text(self, text: str) -> Dict[str, str]:
        if not text:
            return {}
        lines = text.split('\n')
        sections: Dict[str, List[str]] = collections.defaultdict(list)
        current_section = 'preamble'
        heading_pattern = re.compile('^(?:\\d+\\.?\\s*)?(abstract|introduction|related work|background|methodology|method|approach|architecture|model|experiments?|evaluation|results?|discussion|conclusions?|future work|limitations?|acknowledgements?|references|appendix|supplementary|glossary|index)', re.IGNORECASE)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            match = heading_pattern.match(stripped)
            if match:
                current_section = match.group(1).lower().replace(' ', '_')
            else:
                sections[current_section].append(stripped)
        result = {}
        for k, v in sections.items():
            joined = ' '.join(v)
            result[k] = joined[:800]
        return result

    def _extract_entities(self, texts: List[str]) -> Dict[str, List[str]]:
        full = ' '.join(texts)
        entities: Dict[str, List[str]] = {}
        for kind, pattern in _ENTITY_PATTERNS.items():
            found = pattern.findall(full)
            seen_lower = set()
            deduped = []
            for item in found:
                il = item.lower()
                if il not in seen_lower:
                    seen_lower.add(il)
                    deduped.append(item)
            final = []
            for item in deduped:
                il = item.lower()
                if any((il != other.lower() and il in other.lower() for other in deduped)):
                    continue
                final.append(item)
            if final:
                entities[kind] = final[:8]
        return entities

    def _extract_entities_structured(self, texts: List[str]) -> List[Dict]:
        raw = self._extract_entities(texts)
        result = []
        kind_labels = {'model': 'Model / Technology', 'dataset': 'Dataset', 'framework': 'Framework / Tool', 'metric': 'Metric'}
        for kind, items in raw.items():
            for item in items:
                result.append({'entity': item, 'kind': kind, 'label': kind_labels.get(kind, kind)})
        return result

    def _extract_metrics(self, texts: List[str]) -> List[Dict]:
        full = ' '.join(texts)
        results = []
        sentences = self._extract_sentences(full)
        section_number_pattern = re.compile('^\\d+\\.?\\d*\\s|(?:section|table|figure|chapter|appendix)\\s+\\d', re.IGNORECASE)
        seen = set()
        for sent in sentences:
            metric_m = _METRIC_PATTERNS.search(sent)
            value_m = _VALUE_PATTERNS.search(sent)
            if metric_m and value_m:
                value_str = value_m.group()
                value_pos = sent.find(value_str)
                prefix_before_value = sent[:value_pos].strip()
                if section_number_pattern.search(prefix_before_value):
                    continue
                try:
                    num_val = float(value_str.replace('%', '').replace('pp', '').strip())
                    if value_pos < 5 and num_val < 100:
                        remaining = sent[value_pos + len(value_str):].strip()
                        if remaining and remaining[0].isupper() and (len(remaining.split()[0]) > 3):
                            continue
                except (ValueError, IndexError):
                    pass
                metric_name = metric_m.group()
                if metric_name.lower() in ('map', 'ter', 'cer', 'wer'):
                    metric_context_words = ('score', 'value', 'result', 'achieve', 'obtain', 'precision', 'recall')
                    if not any((w in sent.lower() for w in metric_context_words)):
                        continue
                dedup_key = f'{metric_name.lower()}_{value_str}'
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                results.append({'metric': metric_m.group(), 'value': value_m.group(), 'context': sent[:150]})
            if len(results) >= 6:
                break
        return results

    def _extract_findings(self, chunks: List[Dict], keywords: List[str], doc: Dict=None) -> List[str]:
        texts = [(c.get('text') or '').strip() for c in chunks if c.get('text')]
        if not texts and doc and doc.get('extracted_text'):
            texts = [doc.get('extracted_text')]
        if not texts:
            return []
        raw_text = (doc or {}).get('extracted_text') or ''
        if raw_text:
            sections = self._detect_sections_from_text(raw_text)
        else:
            sections = self._detect_sections(chunks)
        priority_texts = []
        for section_key in ('results', 'conclusions', 'conclusion', 'findings', 'discussion'):
            if section_key in sections:
                priority_texts.append(sections[section_key])
        all_text = ' '.join(texts)
        sentences = self._extract_sentences(all_text)
        scored = self._score_sentences(sentences, keywords)
        scored.sort(key=lambda x: x[0], reverse=True)
        finding_markers = re.compile('\\b(show|demonstrate|achieve|outperform|improve|propose|present|introduce|establish|find|reveal|validate|confirm|prove|yield|surpass|exceed|reduce|increase|enable|allow|result|suggest|significantly|substantially|notably|importantly|consistently|effectively|successfully|comparatively|outperforms|superior|comparable|competitive|effective|efficient|robust|scalable|addresses|tackles|solves|overcomes)\\b', re.IGNORECASE)
        findings = []
        if priority_texts:
            priority_sentences = self._extract_sentences(' '.join(priority_texts))
            for sent in priority_sentences:
                if finding_markers.search(sent) and len(sent.split()) >= 10:
                    findings.append(sent)
                if len(findings) >= 3:
                    break
        for score, sent in scored:
            if len(findings) >= 5:
                break
            if sent in findings:
                continue
            if finding_markers.search(sent) and len(sent.split()) >= 10:
                findings.append(sent)
        return findings

    def _extract_methods(self, chunks: List[Dict], keywords: List[str], doc: Dict=None) -> List[Dict]:
        texts = [(c.get('text') or '').strip() for c in chunks if c.get('text')]
        if not texts and doc and doc.get('extracted_text'):
            texts = [doc.get('extracted_text')]
        if not texts:
            return []
        full_text = ' '.join(texts)
        methods = []
        seen = set()
        proposal_patterns = [(re.compile('(?:we propose|we present|introduce|our approach|our method|the proposed)\\s+(.{10,120})', re.IGNORECASE), 'Proposed approach'), (re.compile('(?:we use|we employ|we adopt|we apply|we leverage|we utilize|we implement)\\s+(.{10,120})', re.IGNORECASE), 'Method used'), (re.compile('(?:using|via|through|by means of|employing|leveraging)\\s+(.{10,120})', re.IGNORECASE), 'Technique')]
        for pattern, label in proposal_patterns:
            for match in pattern.finditer(full_text):
                method_text = match.group(1).strip().rstrip('.,;:')
                method_text = re.sub('[^\\x20-\\x7E]+', ' ', method_text)
                method_text = re.sub('\\s+', ' ', method_text).strip()
                if len(method_text) > 120:
                    sent_end = method_text.find('.')
                    if 20 < sent_end < 120:
                        method_text = method_text[:sent_end]
                if method_text and len(method_text) > 10 and (method_text.lower() not in seen):
                    seen.add(method_text.lower())
                    methods.append({'name': method_text[:120], 'description': label})
            if len(methods) >= 4:
                break
        named_patterns = [(re.compile('(?:algorithm|technique|framework|architecture|pipeline|procedure|mechanism)\\s+(?:called|named|termed|referred to as)\\s+(\\S+(?:\\s+\\S+){0,5})', re.IGNORECASE), 'Named algorithm'), (re.compile('(\\w+(?:\\s+\\w+){1,5})\\s+(?:algorithm|method|approach|technique|model|network|architecture|framework)', re.IGNORECASE), 'Technical method')]
        for pattern, label in named_patterns:
            for match in pattern.finditer(full_text):
                method_text = match.group(1).strip().rstrip('.,;:')
                method_text = re.sub('[^\\x20-\\x7E]+', ' ', method_text)
                method_text = re.sub('\\s+', ' ', method_text).strip()
                if method_text and len(method_text) > 5 and (method_text.lower() not in seen):
                    seen.add(method_text.lower())
                    methods.append({'name': method_text[:120], 'description': label})
            if len(methods) >= 6:
                break
        if not methods:
            method_keywords = [kw for kw in keywords[:10] if any((marker in kw.lower() for marker in ['net', 'model', 'approach', 'method', 'algo', 'arch', 'framework', 'transformer', 'attention', 'encoder', 'decoder', 'loss', 'optim', 'retrieval', 'generation', 'augmented', 'dense', 'passage']))]
            for kw in method_keywords[:4]:
                methods.append({'name': kw, 'description': 'Key technical concept'})
        return methods[:6]

    def analyze_summary(self, doc: Dict, chunks: List[Dict], doc_type: str) -> Dict:
        if hasattr(doc, 'keys'):
            doc = dict(doc)
        texts = [(c.get('text') or '').strip() for c in chunks if c.get('text')]
        all_text = (doc.get('extracted_text') or '') + ' '.join(texts)
        texts = texts or [all_text]
        keywords = self._tfidf_keywords(texts, top_k=12)
        extractive = self._extractive_summary(chunks, doc=doc, num_sentences=5, doc_type=doc_type)
        if doc_type == 'research_paper':
            raw_text = doc.get('extracted_text') or ''
            sections = self._detect_sections_from_text(raw_text) if raw_text else self._detect_sections(chunks)
            entities = self._extract_entities(texts)
            metrics = self._extract_metrics(texts)
            seen_m = set()
            deduped_metrics = []
            for m in metrics:
                mk = m['metric'].lower()
                if mk not in seen_m:
                    seen_m.add(mk)
                    deduped_metrics.append(m)
            metrics = deduped_metrics
            findings = self._extract_findings(chunks, keywords, doc=doc)

            def _sec(key: str) -> Optional[str]:
                v = sections.get(key, '').strip()
                if not v:
                    return None
                lines = v.split('\n')
                content_lines = []
                for line in lines:
                    stripped = line.strip()
                    if re.match('^(?:\\d+\\.?\\d*\\s*)?(?:' + key.replace('_', '|') + ')\\s*$', stripped, re.IGNORECASE):
                        continue
                    if re.match('^\\d+\\.\\d+\\s*$', stripped):
                        continue
                    content_lines.append(stripped)
                content = ' '.join(content_lines).strip()
                if not content:
                    content = v
                sentences = self._extract_sentences(content)
                meaningful = [s for s in sentences if len(s.split()) >= 8][:3]
                if meaningful:
                    return ' '.join(meaningful)[:500]
                return content[:500] if content else None
            abstract_text = _sec('abstract') or ''
            intro_text = _sec('introduction') or ''
            research_problem = None
            if intro_text:
                intro_sentences = self._extract_sentences(intro_text)
                problem_markers = re.compile('\\b(problem|challenge|gap|limitation|issue|difficulty|lack|absence|need|require|demand|overcome|address|tackle|solve|question|objective|goal|aim)\\b', re.IGNORECASE)
                for sent in intro_sentences:
                    if problem_markers.search(sent) and len(sent.split()) >= 8:
                        research_problem = sent[:400]
                        break
                if not research_problem:
                    for sent in intro_sentences:
                        if len(sent.split()) >= 10:
                            research_problem = sent[:400]
                            break
            if not research_problem and abstract_text:
                research_problem = abstract_text[:350]
            background = None
            if abstract_text:
                background = abstract_text[:400]
            elif intro_text:
                intro_sentences = self._extract_sentences(intro_text)
                background_sents = [s for s in intro_sentences[:5] if len(s.split()) >= 8]
                background = ' '.join(background_sents[:2])[:400] if background_sents else None
            methodology = _sec('methodology') or _sec('method') or _sec('approach') or _sec('architecture') or _sec('model')
            proposed_approach = methodology
            conclusion = _sec('conclusions') or _sec('conclusion')
            return {'title': doc.get('title') or doc.get('filename'), 'authors': doc.get('author') or None, 'year': doc.get('year'), 'venue': None, 'research_problem': research_problem, 'research_objective': intro_text[:300] if intro_text and (not research_problem) else research_problem, 'background': background, 'proposed_approach': proposed_approach[:500] if proposed_approach else None, 'methodology': methodology[:500] if methodology else None, 'dataset': ', '.join(entities.get('dataset', [])) or None, 'models_algorithms': ', '.join(entities.get('model', [])) or None, 'experimental_setup': _sec('experiments') or _sec('evaluation') or _sec('experimental_setup') or None, 'evaluation_metrics': ', '.join((f"{m['metric']} ({m['value']})" for m in metrics)) or None, 'main_results': _sec('results') or (findings[0] if findings else None), 'key_findings': ' '.join(findings[:3]) if findings else _sec('results') or None, 'main_contribution': findings[0] if findings else extractive[:300] or None, 'limitations': _sec('limitations') or None, 'future_work': _sec('future_work') or _sec('future directions') or None, 'conclusion': conclusion[:400] if conclusion else findings[-1] if findings else None, 'keywords': [kw for kw in keywords if kw.lower() not in _GENERIC_CONCEPT_WORDS][:8], '_analysis_engine': 'local'}
        elif doc_type == 'technical_document':
            raw_text = doc.get('extracted_text') or ''
            sections = self._detect_sections_from_text(raw_text) if raw_text else self._detect_sections(chunks)
            return {'title': doc.get('title') or doc.get('filename'), 'kind': None, 'purpose': extractive[:300] or None, 'audience': None, 'key_concepts': [kw for kw in keywords[:8] if kw.lower() not in _GENERIC_CONCEPT_WORDS], 'main_sections': [{'heading': k.replace('_', ' ').title(), 'summary': v[:250]} for k, v in list(sections.items())[:6] if v], 'api_or_commands': [], 'requirements': [], 'examples': [], '_analysis_engine': 'local'}
        else:
            raw_text = doc.get('extracted_text') or ''
            sections = self._detect_sections_from_text(raw_text) if raw_text else self._detect_sections(chunks)
            all_sentences = self._extract_sentences(' '.join(texts or [all_text]))
            scored = self._score_sentences(all_sentences, keywords)
            scored.sort(key=lambda x: x[0], reverse=True)
            key_points = [s for _, s in scored[:8] if len(s.split()) >= 8]
            return {'title': doc.get('title') or doc.get('filename'), 'summary': extractive[:500] or None, 'key_points': key_points, 'topics': [kw for kw in keywords[:8] if kw.lower() not in _GENERIC_CONCEPT_WORDS], 'document_structure': [{'heading': k.replace('_', ' ').title(), 'content_preview': v[:200]} for k, v in sections.items() if v.strip()], '_analysis_engine': 'local'}

    def analyze_insights(self, doc: Dict, chunks: List[Dict], doc_type: str) -> Dict:
        if hasattr(doc, 'keys'):
            doc = dict(doc)
        texts = [(c.get('text') or '').strip() for c in chunks if c.get('text')]
        all_text = (doc.get('extracted_text') or '') + ' '.join(texts)
        texts = texts or [all_text]
        keywords = self._tfidf_keywords(texts, top_k=15)
        entities = self._extract_entities(texts or [all_text])
        structured_entities = self._extract_entities_structured(texts or [all_text])
        metrics = self._extract_metrics(texts or [all_text])
        findings = self._extract_findings(chunks, keywords, doc=doc)
        methods = self._extract_methods(chunks, keywords, doc=doc)
        key_concepts = []
        for kw in keywords[:10]:
            if kw.lower() not in _GENERIC_CONCEPT_WORDS and len(kw) > 2:
                desc = 'Key technical term identified in the document.'
                kw_lower = kw.lower()
                if any((t in kw_lower for t in ['retrieval', 'search', 'fetch', 'retrieve'])):
                    desc = 'Related to information retrieval'
                elif any((t in kw_lower for t in ['generation', 'generate', 'generative'])):
                    desc = 'Related to text generation'
                elif any((t in kw_lower for t in ['model', 'network', 'architecture'])):
                    desc = 'Model or architecture component'
                elif any((t in kw_lower for t in ['parametric', 'memory', 'encoder', 'decoder'])):
                    desc = 'Architecture component'
                elif any((t in kw_lower for t in ['training', 'learning', 'optimization'])):
                    desc = 'Related to training methodology'
                elif any((t in kw_lower for t in ['dataset', 'data', 'corpus'])):
                    desc = 'Dataset or data-related concept'
                elif any((t in kw_lower for t in ['evaluation', 'metric', 'benchmark', 'score'])):
                    desc = 'Evaluation metric or benchmark'
                key_concepts.append({'concept': kw, 'why_it_matters': desc})
        important_entities = []
        for model_name in entities.get('model', [])[:5]:
            important_entities.append({'entity': model_name, 'kind': 'model', 'role': 'Model / Technology'})
        for ds_name in entities.get('dataset', [])[:5]:
            important_entities.append({'entity': ds_name, 'kind': 'dataset', 'role': 'Dataset'})
        for fw_name in entities.get('framework', [])[:3]:
            important_entities.append({'entity': fw_name, 'kind': 'framework', 'role': 'Framework / Tool'})
        for m_name in entities.get('metric', [])[:3]:
            important_entities.append({'entity': m_name, 'kind': 'metric', 'role': 'Evaluation Metric'})
        if not important_entities:
            title = doc.get('title') or doc.get('filename', '')
            important_entities.append({'entity': title, 'kind': 'document', 'role': 'Primary document under analysis'})
        metric_items = []
        seen_metrics = set()
        for m in metrics:
            m_key = m['metric'].lower()
            if m_key not in seen_metrics:
                seen_metrics.add(m_key)
                metric_items.append({'metric': m['metric'], 'value': m['value'], 'context': m['context'][:150]})
        finding_items = [{'finding': _clean_output_text(f)} for f in findings]
        if not finding_items:
            all_sentences = self._extract_sentences(all_text)
            scored = self._score_sentences(all_sentences, keywords)
            scored.sort(key=lambda x: x[0], reverse=True)
            finding_items = [{'finding': _clean_output_text(s)} for _, s in scored[:4] if len(s.split()) >= 8]
        raw_text = doc.get('extracted_text') or ''
        sections = self._detect_sections_from_text(raw_text) if raw_text else self._detect_sections(chunks)
        document_structure = [{'heading': k.replace('_', ' ').title(), 'content_preview': v[:200]} for k, v in sections.items() if v.strip() and k != 'preamble']
        if doc_type in ('research_paper', 'technical_document'):
            return {'key_concepts': key_concepts, 'important_entities': important_entities, 'methods': methods, 'algorithms': [], 'models': [{'name': m, 'purpose': 'Referenced in document'} for m in entities.get('model', [])], 'datasets': [{'name': d, 'role': 'Referenced in document'} for d in entities.get('dataset', [])], 'metrics': metric_items, 'findings': finding_items, 'contributions': [{'contribution': finding_items[0]['finding']} if finding_items else {'contribution': 'Document indexed and available for analysis.'}], 'limitations': [], 'assumptions': [], 'future_directions': [], 'relationships': [], 'document_structure': document_structure, '_analysis_engine': 'local'}
        else:
            return {'key_concepts': key_concepts, 'important_entities': important_entities, 'methods': methods, 'key_points': finding_items, 'topics': [kw for kw in keywords[:8] if kw.lower() not in _GENERIC_CONCEPT_WORDS], 'action_items': [], 'document_structure': document_structure, '_analysis_engine': 'local'}
_local_analysis_engine = LocalAnalysisEngine()

class DocumentAnalysisService:

    def sources(self, document_id: str) -> Dict:
        doc = _load_document_or_404(document_id)
        chunks = _get_chunks_sorted(document_id)
        if not chunks and doc.get('extracted_text'):
            raw_text = doc['extracted_text']
            paras = [p.strip() for p in raw_text.split('\n\n') if p.strip()]
            chunks = [{'id': f'chunk_{i}', 'chunk_index': i + 1, 'page_number': i // 3 + 1, 'text': p} for i, p in enumerate(paras[:30])]
        sources = [{'chunk_id': c['id'], 'chunk_index': c['chunk_index'], 'page_number': c.get('page_number'), 'text': c['text'], 'char_count': len(c.get('text') or '')} for c in chunks]
        return {'document': {'id': doc['id'], 'filename': doc['filename'], 'file_type': doc['file_type'], 'page_count': doc.get('page_count')}, 'sources': sources, 'total_chunks': len(sources), 'confidence': _confidence_label(sources)}

    def summary(self, document_id: str, force_regenerate: bool=False, on_progress: Optional[Callable[[str], None]]=None) -> Dict:
        doc = _load_document_or_404(document_id)
        doc_type = _detect_document_type(doc)
        cached = db.get_document_analysis(document_id, 'summary')
        if cached and (not force_regenerate):
            cached_hash = cached.get('content_hash') or ''
            current_hash = db.get_analysis_content_hash(doc)
            if cached_hash == current_hash:
                content = json.loads(cached['content_json']) if cached.get('content_json') else {}
                is_valid = isinstance(content, dict) and any((v and v != 'Not stated in the document.' for k, v in content.items() if k in ('research_problem', 'background', 'proposed_approach', 'key_findings', 'summary', 'conclusion')))
                if is_valid:
                    return self._build_summary_payload(doc, doc_type, content, cached=cached, regenerated=False)
        chunks = _get_chunks_sorted(document_id)
        if not chunks and (not doc.get('extracted_text')):
            empty = self._empty_payload_for_type(doc_type)
            db.upsert_document_analysis(document_id, 'summary', doc_type, empty, content_text='(no extractable text)', content_hash=db.get_analysis_content_hash(doc), model=None)
            return self._build_summary_payload(doc, doc_type, empty, regenerated=True)
        sampled = _stratified_sample(chunks, MAX_CHUNKS_IN_CONTEXT)
        context = _format_chunks_for_prompt(sampled)
        if on_progress:
            on_progress('structure')
        parsed = _local_analysis_engine.analyze_summary(doc, sampled, doc_type)
        content = self._merge_with_empty(doc_type, parsed, kind='summary')
        if on_progress:
            on_progress('findings')
        content_hash = db.get_analysis_content_hash(doc)
        content_text = self._content_to_text(doc_type, content)
        db.upsert_document_analysis(document_id, 'summary', doc_type, content, content_text=content_text, content_hash=content_hash, model='local-nlp-engine')
        return self._build_summary_payload(doc, doc_type, content, regenerated=True)

    def insights(self, document_id: str, force_regenerate: bool=False, on_progress: Optional[Callable[[str], None]]=None) -> Dict:
        doc = _load_document_or_404(document_id)
        doc_type = _detect_document_type(doc)
        cached = db.get_document_analysis(document_id, 'insights')
        if cached and (not force_regenerate):
            cached_hash = cached.get('content_hash') or ''
            current_hash = db.get_analysis_content_hash(doc)
            if cached_hash == current_hash:
                content = json.loads(cached['content_json']) if cached.get('content_json') else {}
                is_valid = isinstance(content, dict) and any((isinstance(v, list) and len(v) > 0 for v in content.values()))
                if is_valid:
                    return self._build_insights_payload(doc, doc_type, content, cached=cached, regenerated=False)
        chunks = _get_chunks_sorted(document_id)
        if not chunks and (not doc.get('extracted_text')):
            empty = self._empty_payload_for_type(doc_type, kind='insights')
            db.upsert_document_analysis(document_id, 'insights', doc_type, empty, content_text='(no extractable text)', content_hash=db.get_analysis_content_hash(doc), model=None)
            return self._build_insights_payload(doc, doc_type, empty, regenerated=True)
        sampled = _stratified_sample(chunks, MAX_CHUNKS_IN_CONTEXT)
        context = _format_chunks_for_prompt(sampled)
        if on_progress:
            on_progress('extracting')
        parsed = _local_analysis_engine.analyze_insights(doc, sampled, doc_type)
        content = self._merge_with_empty(doc_type, parsed, kind='insights')
        if on_progress:
            on_progress('relationships')
        content_hash = db.get_analysis_content_hash(doc)
        content_text = self._content_to_text(doc_type, content, kind='insights')
        db.upsert_document_analysis(document_id, 'insights', doc_type, content, content_text=content_text, content_hash=content_hash, model='local-nlp-engine')
        return self._build_insights_payload(doc, doc_type, content, regenerated=True)

    @staticmethod
    def _active_provider_name() -> Optional[str]:
        try:
            from ai.llm_service import llm_service
            names = llm_service.provider_names
            return names[0] if names else None
        except Exception:
            return None

    def _summary_prompt_for_type(self, doc_type: str, context: str) -> str:
        base = _BASE_RULES
        if doc_type == 'research_paper':
            return _PAPER_SUMMARY_PROMPT.format(base=base, context=context)
        if doc_type == 'technical_document':
            return _TECHNICAL_SUMMARY_PROMPT.format(base=base, context=context)
        return _GENERAL_SUMMARY_PROMPT.format(base=base, context=context)

    def _insights_prompt_for_type(self, doc_type: str, context: str) -> str:
        base = _BASE_RULES
        if doc_type in ('research_paper', 'technical_document'):
            return _PAPER_INSIGHTS_PROMPT.format(base=base, context=context)
        return _GENERAL_INSIGHTS_PROMPT.format(base=base, context=context)

    def _empty_payload_for_type(self, doc_type: str, kind: str='summary') -> Dict:
        if kind == 'summary':
            if doc_type == 'general':
                return _empty_general_summary()
            return _empty_paper_summary()
        if doc_type == 'general':
            return _empty_general_insights()
        return _empty_paper_insights()

    def _merge_with_empty(self, doc_type: str, parsed: Dict, kind: str) -> Dict:
        empty = self._empty_payload_for_type(doc_type, kind=kind)
        for k, v in empty.items():
            parsed.setdefault(k, v)
        return parsed

    @staticmethod
    def _content_to_text(doc_type: str, content: Dict, kind: str='summary') -> str:
        if kind == 'summary':
            if doc_type == 'general':
                parts = []
                if content.get('summary'):
                    parts.append(content['summary'])
                if content.get('key_points'):
                    parts.append('\n'.join((f'- {p}' for p in content['key_points'])))
                return '\n\n'.join(parts)
            lines = []
            for key in ('research_problem', 'research_objective', 'background', 'proposed_approach', 'methodology', 'dataset', 'models_algorithms', 'experimental_setup', 'evaluation_metrics', 'main_results', 'key_findings', 'main_contribution', 'limitations', 'future_work', 'conclusion', 'purpose', 'audience'):
                val = content.get(key)
                if val and val != 'Not stated in the document.':
                    lines.append(f'{val}')
            return '\n\n'.join(lines)
        return ''

    def _build_summary_payload(self, doc: Dict, doc_type: str, content: Dict, cached: Optional[Dict]=None, regenerated: bool=False) -> Dict:
        sources = [{'chunk_id': c['id'], 'chunk_index': c['chunk_index'], 'page_number': c.get('page_number')} for c in _get_chunks_sorted(doc['id'])]
        return {'document': {'id': doc['id'], 'filename': doc['filename'], 'file_type': doc['file_type'], 'page_count': doc.get('page_count'), 'author': doc.get('author'), 'year': doc.get('year'), 'title': doc.get('title') or doc.get('filename')}, 'document_type': doc_type, 'summary': content, 'sources': sources, 'confidence': _confidence_label(sources), 'regenerated': regenerated, 'cached': cached is not None and (not regenerated), 'generated_at': (cached or {}).get('generated_at'), 'model': (cached or {}).get('model')}

    def _build_insights_payload(self, doc: Dict, doc_type: str, content: Dict, cached: Optional[Dict]=None, regenerated: bool=False) -> Dict:
        sources = [{'chunk_id': c['id'], 'chunk_index': c['chunk_index'], 'page_number': c.get('page_number')} for c in _get_chunks_sorted(doc['id'])]
        return {'document': {'id': doc['id'], 'filename': doc['filename'], 'file_type': doc['file_type'], 'page_count': doc.get('page_count'), 'author': doc.get('author'), 'year': doc.get('year'), 'title': doc.get('title') or doc.get('filename')}, 'document_type': doc_type, 'insights': content, 'sources': sources, 'confidence': _confidence_label(sources), 'regenerated': regenerated, 'cached': cached is not None and (not regenerated), 'generated_at': (cached or {}).get('generated_at'), 'model': (cached or {}).get('model')}
document_analysis_service = DocumentAnalysisService()
