import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import database.database as db
from ai.llm_service import llm_service
logger = logging.getLogger(__name__)

class NotesService:
    KINDS = {'note', 'idea', 'gap', 'hypothesis', 'question', 'methodology', 'observation', 'finding'}

    def list(self, workspace_id: str) -> List[dict]:
        return db.list_notes(workspace_id)

    def create(self, workspace_id: str, title: str, content: str, kind: str='note', source_message_id: Optional[str]=None) -> dict:
        kind = (kind or 'note').lower().strip()
        if kind not in self.KINDS:
            kind = 'note'
        title = (title or '').strip()[:200] or 'Untitled note'
        content = content or ''
        return db.create_note(workspace_id, title, content, kind, source_message_id)

    def update(self, note_id: str, title: str, content: str) -> Optional[dict]:
        note = db.get_note(note_id)
        if not note:
            return None
        return db.update_note(note_id, title, content)

    def delete(self, note_id: str) -> bool:
        return db.delete_note(note_id)

class BriefService:
    EMPTY = {'topic': '', 'problem': '', 'research_question': '', 'objectives': '', 'papers_reviewed': '', 'key_findings': '', 'common_limitations': '', 'potential_gap': '', 'proposed_direction': '', 'open_questions': '', 'current_stage': 'Discovery'}

    def get(self, workspace_id: str) -> dict:
        existing = db.get_research_brief(workspace_id)
        if existing:
            return existing
        return {'workspace_id': workspace_id, **self.EMPTY, 'updated_at': None}

    def update(self, workspace_id: str, fields: Dict) -> dict:
        clean = {k: v for k, v in (fields or {}).items() if k in self.EMPTY}
        return db.upsert_research_brief(workspace_id, clean)

    def auto_draft(self, workspace_id: str) -> dict:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise ValueError('Workspace not found.')
        docs = db.get_documents_for_workspace(workspace_id)
        if not docs:
            return self.update(workspace_id, self.EMPTY)
        chunks_by_doc = {}
        for d in docs:
            doc_chunks = db.get_chunks_for_document(d['id'])
            if doc_chunks:
                chunks_by_doc[d['filename']] = doc_chunks[:6]
        context_blocks = []
        for name, chunks in chunks_by_doc.items():
            block = f'--- Document: {name} ---\n'
            for c in chunks:
                block += c['text'][:1500] + '\n\n'
            context_blocks.append(block)
        context = '\n'.join(context_blocks)[:50000]
        prompt = _BRIEF_AUTODRAFT_PROMPT.format(workspace_name=ws.get('name', 'Workspace'), workspace_description=ws.get('description', ''), document_count=len(docs), document_list=', '.join((d['filename'] for d in docs[:20])), context=context)
        try:
            raw = llm_service.generate_response(prompt, task='research_synthesis')
            parsed = _safe_json_loads(raw)
        except Exception as e:
            logger.warning(f'Brief auto-draft failed: {e}')
            parsed = {}
        fields = {}
        for key in self.EMPTY:
            v = parsed.get(key)
            if isinstance(v, str) and v.strip():
                fields[key] = v.strip()
        fields.setdefault('papers_reviewed', ', '.join((d['filename'] for d in docs)))
        return db.upsert_research_brief(workspace_id, fields)

class ProjectPlanService:
    SECTIONS = ['problem_statement', 'objectives', 'requirements', 'architecture', 'technology_stack', 'components', 'data_flow', 'implementation_stages', 'testing_strategy', 'evaluation_metrics', 'deployment_plan']

    def get(self, workspace_id: str) -> dict:
        existing = db.get_project_plan(workspace_id)
        return existing or {'workspace_id': workspace_id, **{k: '' for k in self.SECTIONS}, 'updated_at': None}

    def update(self, workspace_id: str, fields: Dict) -> dict:
        clean = {k: v for k, v in (fields or {}).items() if k in self.SECTIONS}
        return db.upsert_project_plan(workspace_id, clean)

    def auto_generate(self, workspace_id: str) -> dict:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise ValueError('Workspace not found.')
        brief = db.get_research_brief(workspace_id) or {}
        docs = db.get_documents_for_workspace(workspace_id)
        doc_list = ', '.join((d['filename'] for d in docs)) if docs else '(no papers attached yet)'
        paper_summaries = []
        for d in docs:
            cs = db.get_chunks_for_document(d['id'])
            if cs:
                paper_summaries.append(f"{d['filename']}: {cs[0]['text'][:600]}")
        paper_context = '\n\n'.join(paper_summaries)[:30000]
        prompt = _PROJECT_PLAN_AUTOGEN_PROMPT.format(workspace_name=ws.get('name', 'Workspace'), workspace_description=ws.get('description', ''), brief_topic=brief.get('topic', ''), brief_question=brief.get('research_question', ''), brief_direction=brief.get('proposed_direction', ''), document_list=doc_list, paper_context=paper_context)
        try:
            raw = llm_service.generate_response(prompt, task='project_planning')
            parsed = _safe_json_loads(raw)
        except Exception as e:
            logger.warning(f'Project plan auto-generate failed: {e}')
            parsed = {}
        fields = {}
        for key in self.SECTIONS:
            v = parsed.get(key)
            if isinstance(v, str) and v.strip():
                fields[key] = v.strip()
        return db.upsert_project_plan(workspace_id, fields)

class ExperimentsService:

    def list(self, workspace_id: str) -> List[dict]:
        return db.list_experiments(workspace_id)

    def create(self, workspace_id: str, name: str, **fields) -> dict:
        if not (name or '').strip():
            raise ValueError('Experiment name is required.')
        return db.create_experiment(workspace_id, name.strip(), **fields)

    def update(self, experiment_id: str, **fields) -> Optional[dict]:
        return db.update_experiment(experiment_id, **fields)

    def delete(self, experiment_id: str) -> bool:
        return db.delete_experiment(experiment_id)

    def analytics(self, workspace_id: str) -> dict:
        rows = db.list_experiments(workspace_id)
        if not rows:
            return {'total': 0, 'by_metric': {}, 'best_per_metric': [], 'unparseable_results': []}
        by_metric = {}
        unparseable = []
        for r in rows:
            m = (r.get('metric') or 'unspecified').strip() or 'unspecified'
            by_metric.setdefault(m, []).append(r)
            raw_result = r.get('result')
            if raw_result is None or (isinstance(raw_result, str) and (not raw_result.strip())):
                continue
            try:
                float(str(raw_result).replace(',', ''))
            except Exception:
                unparseable.append({'experiment_id': r.get('id'), 'experiment_name': r.get('name'), 'metric': m, 'result': raw_result, 'reason': 'Result is not numeric; excluded from best-per-metric ranking.'})
        best = []
        for m, items in by_metric.items():
            numeric = []
            for it in items:
                try:
                    numeric.append((float(str(it.get('result')).replace(',', '')), it))
                except Exception:
                    pass
            if numeric:
                top = max(numeric, key=lambda x: x[0])
                best.append({'metric': m, 'best_result': top[0], 'experiment_id': top[1]['id'], 'experiment_name': top[1]['name'], 'model': top[1].get('model'), 'dataset': top[1].get('dataset')})
        return {'total': len(rows), 'by_metric': {m: len(v) for m, v in by_metric.items()}, 'best_per_metric': best, 'unparseable_results': unparseable}

class ResearchGapService:

    def analyze(self, workspace_id: str) -> dict:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise ValueError('Workspace not found.')
        docs = db.get_documents_for_workspace(workspace_id)
        if len(docs) < 2:
            return {'workspace_id': workspace_id, 'document_count': len(docs), 'gaps': [], 'themes': [], 'contradictions': [], 'summary': 'Need at least two documents in the workspace to perform gap analysis.', 'evidence': [], 'synthesis': [], 'inference': [], 'possible_directions': []}
        per_doc_chunks = []
        for d in docs[:8]:
            chunks = db.get_chunks_for_document(d['id'])
            if chunks:
                txt = '\n'.join((c['text'][:1200] for c in chunks[:6]))
                per_doc_chunks.append((d['filename'], txt))
        context = '\n\n'.join((f'### {n}\n{t}' for n, t in per_doc_chunks))[:50000]
        prompt = _RESEARCH_GAP_PROMPT.format(workspace_name=ws.get('name', 'Workspace'), document_count=len(docs), document_list=', '.join((d['filename'] for d in docs[:20])), context=context)
        try:
            raw = llm_service.generate_response(prompt, task='research_gap')
            parsed = _safe_json_loads(raw)
        except Exception as e:
            logger.warning(f'Research gap analysis failed: {e}')
            parsed = {}
        return {'workspace_id': workspace_id, 'document_count': len(docs), 'themes': parsed.get('themes', []) or [], 'contradictions': parsed.get('contradictions', []) or [], 'gaps': parsed.get('gaps', []) or [], 'summary': parsed.get('summary', '') or '', 'evidence': parsed.get('evidence', []) or [], 'synthesis': parsed.get('synthesis', []) or [], 'inference': parsed.get('inference', []) or [], 'possible_directions': parsed.get('possible_directions', []) or []}

class SynthesisService:

    def synthesize(self, workspace_id: str, question: Optional[str]=None) -> dict:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise ValueError('Workspace not found.')
        docs = db.get_documents_for_workspace(workspace_id)
        if not docs:
            return {'workspace_id': workspace_id, 'document_count': 0, 'synthesis': 'Add at least one document to the workspace to run a synthesis.', 'sources': [], 'evidence': [], 'inference': [], 'directions': []}
        per_doc_chunks = []
        sources = []
        for d in docs[:10]:
            chunks = db.get_chunks_for_document(d['id'])
            if chunks:
                txt = '\n'.join((c['text'][:1200] for c in chunks[:6]))
                per_doc_chunks.append((d['filename'], txt))
                sources.append({'document_id': d['id'], 'filename': d['filename']})
        context = '\n\n'.join((f'### {n}\n{t}' for n, t in per_doc_chunks))[:60000]
        prompt = _SYNTHESIS_PROMPT.format(workspace_name=ws.get('name', 'Workspace'), workspace_description=ws.get('description', ''), document_count=len(docs), question=(question or 'What do these papers collectively tell us?').strip(), context=context)
        try:
            raw = llm_service.generate_response(prompt, task='research_synthesis')
            parsed = _safe_json_loads(raw)
        except Exception as e:
            logger.warning(f'Synthesis failed: {e}')
            parsed = {}
        return {'workspace_id': workspace_id, 'document_count': len(docs), 'question': question, 'synthesis': parsed.get('synthesis', '') or '', 'evidence': parsed.get('evidence', []) or [], 'inference': parsed.get('inference', []) or [], 'directions': parsed.get('directions', []) or [], 'sources': sources}

def _safe_json_loads(raw: str) -> dict:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith('```json'):
        text = text[7:]
    if text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.debug(f'JSON parse failed: {e}; head: {raw[:200]}')
        return {}
_BRIEF_AUTODRAFT_PROMPT = 'You are ORBOT drafting a Research Brief for the workspace "{workspace_name}".\n\nWorkspace description: {workspace_description}\n\nDocuments attached ({document_count}):\n{document_list}\n\nFrom the supplied document chunks below, draft a structured Research Brief with these sections:\n- topic\n- problem\n- research_question\n- objectives\n- papers_reviewed (one line; we will prepend the file list automatically)\n- key_findings\n- common_limitations\n- potential_gap\n- proposed_direction\n- open_questions\n- current_stage\n\nRules:\n- Use ONLY the supplied document chunks as evidence.\n- If a section cannot be filled, leave it as "".\n- Be concise. Each section 1-3 sentences or a short list.\n- Output STRICT JSON with exactly the keys above. No prose, no fences.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END ===\n'
_PROJECT_PLAN_AUTOGEN_PROMPT = 'You are ORBOT in Project Mode generating a Project Plan for the workspace "{workspace_name}".\n\nWorkspace description: {workspace_description}\n\nBrief context:\n- Topic: {brief_topic}\n- Research question: {brief_question}\n- Proposed direction: {brief_direction}\n\nAttached papers:\n{document_list}\n\nPaper snippets:\n{paper_context}\n\nGenerate a Project Plan with these sections:\n- problem_statement\n- objectives (bulleted, 3-6 items)\n- requirements (functional + non-functional, bulleted)\n- architecture (short paragraph + bullets for components)\n- technology_stack (bulleted)\n- components (bulleted)\n- data_flow (short paragraph)\n- implementation_stages (numbered list, 4-8 stages)\n- testing_strategy (bulleted)\n- evaluation_metrics (bulleted)\n- deployment_plan (bulleted)\n\nRules:\n- Ground every choice in the papers\' methodology/tech where possible.\n- Be specific. Avoid generic statements.\n- Output STRICT JSON with exactly the keys above. No prose, no fences.\n\n'
_RESEARCH_GAP_PROMPT = 'You are ORBOT performing a research-gap analysis on the workspace "{workspace_name}".\n\nDocuments attached ({document_count}):\n{document_list}\n\nFrom the supplied chunks, identify:\n\n- themes: recurring themes across the documents (array of short strings)\n- contradictions: where documents disagree (array of {topic, side_a, side_b})\n- gaps: limitations repeatedly mentioned, underexplored areas, missing experiments (array of strings)\n- evidence: source-supported facts that justify the gaps above (array of strings)\n- synthesis: what can be concluded from the evidence (array of strings)\n- inference: reasonable interpretations not directly stated (array of strings)\n- possible_directions: actionable research directions the user could investigate (array of strings)\n- summary: 2-4 sentence top-level summary\n\nStrict rules:\n- Only use the supplied chunks as evidence.\n- Clearly distinguish evidence / synthesis / inference / possible direction.\n- Do NOT claim "no one has ever done this" unless the chunks explicitly support it.\n- Output STRICT JSON with the keys above. No prose, no fences.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END ===\n'
_SYNTHESIS_PROMPT = 'You are ORBOT performing a workspace synthesis for "{workspace_name}".\n\nWorkspace description: {workspace_description}\n\nUser question: {question}\n\nDocuments attached: {document_count}\n\nFrom the supplied chunks, answer the user\'s question and produce:\n- synthesis: 4-8 sentence integrative answer grounded in the documents\n- evidence: source-supported facts (array of strings, each citing which paper)\n- inference: reasonable interpretations (array of strings)\n- directions: 1-3 research directions that follow from the synthesis\n\nRules:\n- Only use the supplied chunks.\n- Clearly distinguish evidence vs inference.\n- Output STRICT JSON with the keys above. No prose, no fences.\n\n=== DOCUMENT CHUNKS ===\n{context}\n=== END ===\n'
notes_service = NotesService()
brief_service = BriefService()
project_plan_service = ProjectPlanService()
experiments_service = ExperimentsService()
research_gap_service = ResearchGapService()
synthesis_service = SynthesisService()
