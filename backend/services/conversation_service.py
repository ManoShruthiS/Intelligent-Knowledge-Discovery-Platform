from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import database.database as db
logger = logging.getLogger(__name__)

def ensure_conversation(*, user_id: Optional[str], scope: str, workspace_id: Optional[str]=None, title: Optional[str]=None, mode: str='research', conversation_id: Optional[str]=None) -> Dict:
    if conversation_id:
        existing = db.get_conversation(conversation_id)
        if existing:
            if mode and existing.get('mode') != mode:
                return db.update_conversation(conversation_id, mode=mode) or existing
            return existing
    return db.create_conversation(user_id=user_id, scope=scope, workspace_id=workspace_id, title=title, mode=mode)

def save_message(conversation_id: str, *, role: str, content: str, sources: Optional[List[dict]]=None, trace: Optional[str]=None, confidence: Optional[str]=None, metadata: Optional[dict]=None, suggested_followups: Optional[List[str]]=None, insufficient_evidence: bool=False) -> Dict:
    return db.append_message(conversation_id, role=role, content=content, sources=sources, trace=trace, confidence=confidence, metadata=metadata, suggested_followups=suggested_followups, insufficient_evidence=insufficient_evidence)

def load_history(conversation_id: str, max_messages: int=16) -> List[Dict]:
    return db.list_messages_as_history(conversation_id, max_messages=max_messages)

def list_for_user(*, user_id: Optional[str], scope: Optional[str]=None, workspace_id: Optional[str]=None, limit: int=50) -> List[Dict]:
    return db.list_conversations(user_id=user_id, scope=scope, workspace_id=workspace_id, limit=limit)

def get(conversation_id: str) -> Optional[Dict]:
    return db.get_conversation(conversation_id)

def messages_of(conversation_id: str) -> List[Dict]:
    return db.list_messages(conversation_id)

def rename(conversation_id: str, title: str) -> Optional[Dict]:
    return db.update_conversation(conversation_id, title=title)

def remove(conversation_id: str) -> bool:
    return db.delete_conversation(conversation_id)

def delete_tail(conversation_id: str, after_index: int) -> int:
    return db.delete_messages_after(conversation_id, after_index)

def _format_message_md(m: Dict, idx: int) -> str:
    role = m.get('role') or '?'
    content = (m.get('content') or '').strip()
    sources = m.get('sources_json') or []
    confidence = m.get('confidence')
    trace = m.get('trace')
    metadata = m.get('metadata_json') or {}
    followups = m.get('suggested_followups_json') or []
    header_role = 'User' if role == 'user' else 'ORBOT'
    label = f'### {idx + 1}. {header_role}'
    if role == 'orbot':
        conf = confidence or 'unverified'
        label += f'  _(confidence: {conf})_'
    parts = [label, '', content, '']
    if trace:
        parts += ['**Trace:**', '```', trace, '```', '']
    if sources:
        parts.append('**Sources:**')
        for s in sources:
            fname = s.get('filename') or 'Unknown'
            page = s.get('page_number')
            sim = s.get('similarity')
            sim_str = f' — relevance {max(0, min(1, 1 - (sim or 0))):.2f}' if isinstance(sim, (int, float)) else ''
            page_str = f' (page {page})' if page is not None else ''
            parts.append(f'- `{fname}`{page_str}{sim_str}')
        parts.append('')
    if followups and role == 'orbot':
        parts.append('**Follow-ups:**')
        for f in followups:
            parts.append(f'- {f}')
        parts.append('')
    if metadata:
        provider = metadata.get('provider')
        llm_ms = metadata.get('llm_latency_ms')
        ret_ms = metadata.get('retrieval_latency_ms')
        meta_bits = []
        if provider:
            meta_bits.append(f'provider: {provider}')
        if isinstance(ret_ms, (int, float)):
            meta_bits.append(f'retrieval: {ret_ms} ms')
        if isinstance(llm_ms, (int, float)):
            meta_bits.append(f'generation: {llm_ms} ms')
        if meta_bits:
            parts.append(f"_{' · '.join(meta_bits)}_")
            parts.append('')
    return '\n'.join(parts)

def export_markdown(conversation_id: str, *, include_metadata: bool=True) -> str:
    conv = db.get_conversation(conversation_id)
    if not conv:
        raise ValueError('Conversation not found.')
    msgs = db.list_messages(conversation_id)
    title = conv.get('title') or 'Conversation'
    scope = conv.get('scope') or 'home'
    mode = conv.get('mode') or 'research'
    created = conv.get('created_at') or ''
    updated = conv.get('updated_at') or ''
    lines = [f'# {title}', '', f'_Scope: {scope} · Mode: {mode}_', f'_Created: {created} · Updated: {updated}_', f'_Exported: {datetime.utcnow().isoformat()}_', '', '---', '']
    if include_metadata:
        lines += ['## Conversation metadata', '', f'- Conversation ID: `{conversation_id}`', f'- Scope: `{scope}`', f'- Mode: `{mode}`', f"- Workspace ID: `{conv.get('workspace_id') or '—'}`", f'- Messages: {len(msgs)}', '', '---', '']
    for i, m in enumerate(msgs):
        lines.append(_format_message_md(m, i))
        lines.append('---')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'

def export_plain_text(conversation_id: str) -> str:
    md = export_markdown(conversation_id, include_metadata=True)
    out = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith('```'):
            in_code = not in_code
            out.append('')
            continue
        if in_code:
            out.append(line)
            continue
        if line.startswith('### '):
            out.append(line[4:].strip())
        elif line.startswith('## '):
            out.append(line[3:].strip().upper())
        elif line.startswith('# '):
            out.append(line[2:].strip().upper())
            out.append('=' * max(8, len(line[2:].strip())))
        elif line.startswith('- '):
            out.append('  * ' + line[2:].strip())
        elif line.startswith('---'):
            out.append('')
        else:
            out.append(line)
    return '\n'.join(out).rstrip() + '\n'

def export_single_answer(*, conversation_id: Optional[str], user_question: str, answer: str, sources: Optional[List[Dict]]=None, trace: Optional[str]=None, confidence: Optional[str]=None, metadata: Optional[Dict]=None, title: Optional[str]=None, followups: Optional[List[str]]=None, format: str='markdown') -> str:
    title = (title or 'ORBOT answer').strip()[:120] or 'ORBOT answer'
    if (format or 'markdown').lower().startswith('txt') or (format or '').lower() == 'text':
        lines = [title.upper(), '=' * max(8, len(title)), '']
        lines.append('Question:')
        lines.append(user_question.strip())
        lines.append('')
        lines.append('Answer:')
        lines.append(answer.strip())
        lines.append('')
        if sources:
            lines.append('Sources:')
            for s in sources:
                fname = s.get('filename') or 'Unknown'
                page = s.get('page_number')
                sim = s.get('similarity')
                sim_str = ''
                if isinstance(sim, (int, float)):
                    sim_str = f' — relevance {max(0, min(1, 1 - sim)):.2f}'
                page_str = f' (page {page})' if page is not None else ''
                lines.append(f'  - {fname}{page_str}{sim_str}')
            lines.append('')
        if confidence:
            lines.append(f'Confidence: {confidence}')
        if trace:
            lines.append('')
            lines.append('Trace:')
            lines.append(trace)
        if metadata:
            bits = []
            if metadata.get('provider'):
                bits.append(f"provider: {metadata['provider']}")
            if isinstance(metadata.get('llm_latency_ms'), (int, float)):
                bits.append(f"generation: {metadata['llm_latency_ms']} ms")
            if isinstance(metadata.get('retrieval_latency_ms'), (int, float)):
                bits.append(f"retrieval: {metadata['retrieval_latency_ms']} ms")
            if bits:
                lines.append('Metadata: ' + ' · '.join(bits))
        if followups:
            lines.append('')
            lines.append('Follow-ups:')
            for f in followups:
                lines.append(f'  - {f}')
        if conversation_id:
            lines.append('')
            lines.append(f'Conversation ID: {conversation_id}')
        lines.append('')
        lines.append(f'Exported: {datetime.utcnow().isoformat()}')
        return '\n'.join(lines).rstrip() + '\n'
    lines = [f'# {title}', '']
    if conversation_id:
        lines.append(f'_Conversation ID: `{conversation_id}`_')
        lines.append('')
    lines.append('## Question')
    lines.append('')
    lines.append(user_question.strip())
    lines.append('')
    lines.append('## Answer')
    lines.append('')
    lines.append(answer.strip())
    lines.append('')
    if sources:
        lines.append('## Sources')
        lines.append('')
        for s in sources:
            fname = s.get('filename') or 'Unknown'
            page = s.get('page_number')
            sim = s.get('similarity')
            sim_str = ''
            if isinstance(sim, (int, float)):
                sim_str = f' — relevance {max(0, min(1, 1 - sim)):.2f}'
            page_str = f' (page {page})' if page is not None else ''
            lines.append(f'- `{fname}`{page_str}{sim_str}')
        lines.append('')
    if confidence:
        lines.append(f'**Confidence:** {confidence}')
        lines.append('')
    if trace:
        lines += ['**Trace:**', '', '```', trace, '```', '']
    if metadata:
        bits = []
        if metadata.get('provider'):
            bits.append(f"provider: {metadata['provider']}")
        if isinstance(metadata.get('llm_latency_ms'), (int, float)):
            bits.append(f"generation: {metadata['llm_latency_ms']} ms")
        if isinstance(metadata.get('retrieval_latency_ms'), (int, float)):
            bits.append(f"retrieval: {metadata['retrieval_latency_ms']} ms")
        if bits:
            lines.append(f"_Metadata: {' · '.join(bits)}_")
            lines.append('')
    if followups:
        lines += ['**Follow-ups:**']
        for f in followups:
            lines.append(f'- {f}')
        lines.append('')
    lines.append(f'_Exported: {datetime.utcnow().isoformat()}_')
    lines.append('')
    return '\n'.join(lines).rstrip() + '\n'
conversation_service = type('ConvService', (), {})()
conversation_service.ensure_conversation = staticmethod(ensure_conversation)
conversation_service.save_message = staticmethod(save_message)
conversation_service.load_history = staticmethod(load_history)
conversation_service.list_for_user = staticmethod(list_for_user)
conversation_service.get = staticmethod(get)
conversation_service.messages_of = staticmethod(messages_of)
conversation_service.rename = staticmethod(rename)
conversation_service.remove = staticmethod(remove)
conversation_service.delete_tail = staticmethod(delete_tail)
conversation_service.export_markdown = staticmethod(export_markdown)
conversation_service.export_plain_text = staticmethod(export_plain_text)
conversation_service.export_single_answer = staticmethod(export_single_answer)
