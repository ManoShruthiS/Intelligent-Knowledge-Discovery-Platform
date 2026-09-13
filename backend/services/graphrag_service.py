from __future__ import annotations
import json
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence
from ai.config import KNO_GRAPHRAG, KNO_GRAPHRAG_FALLBACK_SQLITE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from ai.llm_service import llm_service
logger = logging.getLogger(__name__)
try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None
try:
    import networkx as nx
except ImportError:
    nx = None
EXTRACT_PROMPT = 'You are an information-extraction assistant. Given a\ndocument chunk, return a JSON object describing the salient entities and\ntheir relationships.\n\nFormat (no prose, no Markdown):\n{{\n  "entities": [\n    {{"name": "...", "type": "person|method|dataset|metric|concept|other", "weight": 1..3}}\n  ],\n  "relationships": [\n    {{"source": "...", "target": "...", "label": "short verb phrase", "weight": 1..3}}\n  ]\n}}\n\nRules:\n- 0–8 entities per chunk, dedup within the chunk.\n- 0–8 relationships.\n- Lower-case names. Trim whitespace.\n- Skip generic entities ("paper", "section", "study", "we") unless the\n  chunk is too sparse to be useful without them.\n\nChunk:\n"""\n{chunk}\n"""\n\nJSON:'

def _parse_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    text = text.strip()
    if text.startswith('```'):
        text = re.sub('^```(?:json)?', '', text, count=1).strip().strip('`').strip()
    m = re.search('\\{.*\\}', text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def extract_entities(chunk_text: str) -> Dict:
    empty = {'entities': [], 'relationships': []}
    if not chunk_text or not llm_service.is_configured:
        return empty
    try:
        prompt = EXTRACT_PROMPT.format(chunk=chunk_text[:2000])
        raw = llm_service.generate_response(prompt, task='research_analysis')
        parsed = _parse_json(raw)
        if not parsed:
            return empty
        ents = parsed.get('entities') or []
        rels = parsed.get('relationships') or []
        return {'entities': [{'name': str(e.get('name') or '').strip().lower(), 'type': str(e.get('type') or 'other'), 'weight': int(e.get('weight') or 1)} for e in ents if e.get('name')], 'relationships': [{'source': str(r.get('source') or '').strip().lower(), 'target': str(r.get('target') or '').strip().lower(), 'label': str(r.get('label') or '').strip().lower(), 'weight': int(r.get('weight') or 1)} for r in rels if r.get('source') and r.get('target')]}
    except Exception as exc:
        logger.debug('Entity extraction failed: %s', exc)
        return empty

class _Neo4jBackend:

    def __init__(self):
        if GraphDatabase is None:
            raise RuntimeError('neo4j package not installed')
        if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
            raise RuntimeError('Neo4j env vars (NEO4J_URI/USER/PASSWORD) not set')
        self._driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._init_schema()

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass

    def _init_schema(self) -> None:
        try:
            with self._driver.session() as session:
                session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE')
                session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE')
        except Exception as exc:
            logger.warning('Neo4j schema init failed: %s', exc)

    def add_chunk_kg(self, chunk_id: str, document_id: str, kg: Dict) -> None:
        try:
            with self._driver.session() as session:
                session.run('MERGE (c:Chunk {id:$id}) SET c.document_id=$doc, c.text=$text', id=chunk_id, doc=document_id, text='')
                for ent in kg.get('entities', []):
                    session.run('MERGE (e:Entity {name:$n}) SET e.type=$t MERGE (c:Chunk {id:$cid}) MERGE (c)-[r:MENTIONS]->(e) ON CREATE SET r.weight=$w', n=ent['name'], t=ent.get('type', 'other'), cid=chunk_id, w=int(ent.get('weight', 1)))
                for rel in kg.get('relationships', []):
                    session.run('MATCH (s:Entity {name:$s}), (t:Entity {name:$t}) MERGE (s)-[r:RELATES {label:$l}]->(t) ON CREATE SET r.weight=$w', s=rel['source'], t=rel['target'], l=rel.get('label', 'related'), w=int(rel.get('weight', 1)))
        except Exception as exc:
            logger.warning('Neo4j add_chunk_kg failed: %s', exc)

    def remove_document(self, document_id: str) -> None:
        try:
            with self._driver.session() as session:
                session.run('MATCH (c:Chunk {document_id:$doc}) DETACH DELETE c', doc=document_id)
        except Exception as exc:
            logger.warning('Neo4j remove_document failed: %s', exc)

    def community_summaries_for_entities(self, entity_names: List[str]) -> List[Dict]:
        try:
            with self._driver.session() as session:
                result = session.run('MATCH (e:Entity)-[:IN_COMMUNITY]->(c:Community) WHERE e.name IN $names RETURN DISTINCT c.id AS id, c.summary AS summary', names=entity_names)
                return [{'id': r['id'], 'summary': r['summary']} for r in result]
        except Exception as exc:
            logger.warning('Neo4j community query failed: %s', exc)
            return []

class _InMemoryBackend:

    def __init__(self):
        if nx is None:
            raise RuntimeError('networkx not installed')
        self._graph = nx.DiGraph()
        self._entity_to_chunks: Dict[str, set] = defaultdict(set)
        self._summaries: Dict[str, str] = {}

    def add_chunk_kg(self, chunk_id: str, document_id: str, kg: Dict) -> None:
        for ent in kg.get('entities', []):
            name = ent['name']
            if not self._graph.has_node(name):
                self._graph.add_node(name, type=ent.get('type', 'other'))
            self._entity_to_chunks[name].add(chunk_id)
            self._graph.add_edge(chunk_id, name, kind='MENTIONS', weight=ent.get('weight', 1))
        for rel in kg.get('relationships', []):
            s, t = (rel['source'], rel['target'])
            if not self._graph.has_node(s):
                self._graph.add_node(s, type='other')
            if not self._graph.has_node(t):
                self._graph.add_node(t, type='other')
            self._graph.add_edge(s, t, kind='RELATES', label=rel.get('label', ''), weight=rel.get('weight', 1))

    def remove_document(self, document_id: str) -> None:
        chunk_nodes = [n for n, d in list(self._graph.nodes(data=True)) if str(n).startswith('chunk:')]
        for n in chunk_nodes:
            if self._graph.nodes[n].get('document_id') == document_id:
                self._graph.remove_node(n)

    def community_summaries_for_entities(self, entity_names: List[str]) -> List[Dict]:
        if not self._graph.nodes or not entity_names:
            return []
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            entities = [e for e in entity_names if self._graph.has_node(e)]
            if not entities:
                return []
            sub = self._graph.subgraph(entities + [n for n in self._graph.successors(entities[0]) if self._graph.nodes[n].get('type') not in (None,)])
            undirected = sub.to_undirected()
            for n in list(undirected.nodes()):
                if str(n).startswith('chunk:'):
                    undirected.remove_node(n)
            if not undirected.nodes:
                return []
            comms = list(greedy_modularity_communities(undirected))
        except Exception as exc:
            logger.debug('Community detection failed: %s', exc)
            return []
        results: List[Dict] = []
        for i, members in enumerate(comms):
            cid = f"c{i}-{'-'.join(sorted(members))[:32]}"
            if cid not in self._summaries and llm_service.is_configured:
                try:
                    prompt = f'Write a short paragraph (≤ 80 words) summarising the theme of this topic cluster based on its entity names and the relationships between them. Entities: {sorted(members)}\nRelationships: ' + '; '.join((f"{s} {d.get('label', 'related')} {t}" for s, t, d in self._graph.edges(data=True) if s in members and t in members))[:1500]
                    raw = llm_service.generate_response(prompt, task='research_synthesis')
                    self._summaries[cid] = (raw or '').strip()[:1000] or '(no summary available)'
                except Exception as exc:
                    logger.debug('Community summary failed: %s', exc)
                    self._summaries[cid] = '(summary unavailable)'
            results.append({'id': cid, 'summary': self._summaries.get(cid, '')})
        return results

class GraphRAGService:

    def __init__(self):
        self.backend: Optional[object] = None
        self._ingested_count: int = 0
        self._init_backend()

    @property
    def enabled(self) -> bool:
        if not KNO_GRAPHRAG:
            return False
        return self.backend is not None and self._ingested_count > 0

    def _init_backend(self) -> None:
        if not KNO_GRAPHRAG:
            return
        if NEO4J_URI and NEO4J_PASSWORD and (GraphDatabase is not None):
            try:
                self.backend = _Neo4jBackend()
                logger.info('GraphRAG using Neo4j at %s', NEO4J_URI)
                return
            except Exception as exc:
                logger.warning('Neo4j init failed (%s); trying in-memory backend', exc)
        if KNO_GRAPHRAG_FALLBACK_SQLITE and nx is not None:
            try:
                self.backend = _InMemoryBackend()
                logger.info('GraphRAG using in-memory NetworkX backend')
            except Exception as exc:
                logger.warning('In-memory graph init failed: %s', exc)

    def ingest_chunk(self, chunk_id: str, document_id: str, chunk_text: str) -> None:
        if not self.backend:
            return
        kg = extract_entities(chunk_text)
        if not kg.get('entities') and (not kg.get('relationships')):
            return
        try:
            if isinstance(self.backend, _Neo4jBackend):
                self.backend.add_chunk_kg(f'chunk:{chunk_id}', document_id, kg)
            else:
                self.backend.add_chunk_kg(f'chunk:{chunk_id}', document_id, kg)
            self._ingested_count += 1
        except Exception as exc:
            logger.warning('GraphRAG ingest failed: %s', exc)

    def remove_document(self, document_id: str) -> None:
        if not self.backend:
            return
        try:
            self.backend.remove_document(document_id)
        except Exception as exc:
            logger.warning('GraphRAG remove_document failed: %s', exc)

    def enrich(self, question: str, chunks: List[Dict], workspace_id: Optional[str]=None) -> Dict:
        if not self.enabled:
            return {'chunks': chunks, 'community_summaries': []}
        try:
            text_blob = ' '.join((c.get('text') or '' for c in chunks)).lower()
            candidates = sorted({t for t in re.findall('\\b[a-z][a-z0-9_-]{3,}\\b', question.lower()) if t in text_blob})[:20]
            if not candidates:
                return {'chunks': chunks, 'community_summaries': []}
            summaries = self.backend.community_summaries_for_entities(candidates)
        except Exception as exc:
            logger.debug('GraphRAG enrich failed: %s', exc)
            return {'chunks': chunks, 'community_summaries': []}
        return {'chunks': chunks, 'community_summaries': summaries[:3]}
graphrag_service = GraphRAGService()
