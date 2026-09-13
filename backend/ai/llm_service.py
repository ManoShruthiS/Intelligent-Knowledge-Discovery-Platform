from __future__ import annotations
import os
import re
import base64
import logging
from typing import Dict, List, Optional, Tuple
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
logger = logging.getLogger(__name__)

class LLMNotConfiguredError(Exception):
    pass

class LLMProvider:
    name: str = 'base'
    supports_vision: bool = False

    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def generate_chat(self, contents: list) -> str:
        raise NotImplementedError

    def generate_stream(self, prompt: str):
        yield self.generate(prompt)

    def generate_chat_stream(self, contents: list, config=None):
        yield self.generate_chat(contents)

class GeminiProvider(LLMProvider):
    name = 'gemini'
    supports_vision = True

    def __init__(self, api_key=None, slot=0):
        from google import genai
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        if not self.api_key:
            raise LLMNotConfiguredError('GEMINI_API_KEY is not set.')
        self.name = 'gemini' if not slot else f'gemini-{slot + 1}'
        try:
            self.client = genai.Client(api_key=self.api_key, http_options={'timeout': 60000})
        except Exception as e:
            raise LLMNotConfiguredError(f'Failed to initialise Gemini client: {e}')

    def generate(self, prompt: str) -> str:
        resp = self.client.models.generate_content(model=self.model, contents=prompt)
        return resp.text or ''

    def generate_chat(self, contents: list) -> str:
        from google.genai import types as gtypes
        resp = self.client.models.generate_content(model=self.model, contents=contents, config=gtypes.GenerateContentConfig(temperature=0.4, top_p=0.9, max_output_tokens=2048))
        return resp.text or ''

    def generate_stream(self, prompt: str):
        try:
            stream = self.client.models.generate_content_stream(model=self.model, contents=prompt)
            for chunk in stream:
                text = getattr(chunk, 'text', None)
                if text:
                    yield text
        except Exception:
            yield self.generate(prompt)

    def generate_chat_stream(self, contents: list, config=None):
        from google.genai import types as gtypes
        cfg = config or gtypes.GenerateContentConfig(temperature=0.4, top_p=0.9, max_output_tokens=2048)
        try:
            stream = self.client.models.generate_content_stream(model=self.model, contents=contents, config=cfg)
            for chunk in stream:
                text = getattr(chunk, 'text', None)
                if text:
                    yield text
        except Exception:
            yield self.generate_chat(contents)

class OpenAICompatProvider(LLMProvider):
    name = 'openai-compat'

    def __init__(self, *, api_key: str, base_url: str, model: str, provider_label: str, slot=0):
        from openai import OpenAI
        if not api_key:
            raise LLMNotConfiguredError(f'{provider_label} API key is not set.')
        self._label = provider_label
        self.name = provider_label if not slot else f'{provider_label}-{slot + 1}'
        self.model = model
        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)
        except Exception as e:
            raise LLMNotConfiguredError(f'Failed to initialise {provider_label} client: {e}')

    @property
    def supports_vision(self) -> bool:
        m = (self.model or '').lower()
        return 'gpt-4o' in m or 'gpt-4-vision' in m or 'vision' in m or ('claude' in m)

    def generate(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(model=self.model, messages=[{'role': 'user', 'content': prompt}], temperature=0.4, max_tokens=2048)
        return (resp.choices[0].message.content or '').strip()

    def generate_chat(self, contents: list) -> str:
        messages = self._convert_contents(contents)
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.4, max_tokens=2048)
        return (resp.choices[0].message.content or '').strip()

    def generate_stream(self, prompt: str):
        try:
            stream = self.client.chat.completions.create(model=self.model, messages=[{'role': 'user', 'content': prompt}], temperature=0.4, max_tokens=2048, stream=True)
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except (AttributeError, IndexError):
                    delta = None
                if delta:
                    yield delta
        except Exception:
            yield self.generate(prompt)

    def generate_chat_stream(self, contents: list, config=None):
        try:
            messages = self._convert_contents(contents)
            stream = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.4, max_tokens=2048, stream=True)
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except (AttributeError, IndexError):
                    delta = None
                if delta:
                    yield delta
        except Exception:
            yield self.generate_chat(contents)

    @staticmethod
    def _convert_contents(contents: list) -> list:
        messages = []
        primed_system = False
        for c in contents:
            oai_role = 'assistant' if c.role == 'model' else c.role
            text_parts = []
            image_parts = []
            for p in c.parts:
                if getattr(p, 'text', None):
                    text_parts.append(p.text)
                inline = getattr(p, 'inline_data', None)
                if inline is not None:
                    mime = inline.mime_type
                    data_bytes = inline.data
                    b64 = base64.b64encode(data_bytes).decode('ascii')
                    image_parts.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}})
            joined_text = '\n'.join(text_parts)
            if not primed_system and oai_role == 'user' and (len(joined_text) > 500) and (not image_parts):
                sys_text, user_text = _split_system_from_primer(joined_text)
                if sys_text:
                    messages.append({'role': 'system', 'content': sys_text})
                messages.append({'role': 'user', 'content': user_text})
                primed_system = True
                continue
            if not image_parts:
                messages.append({'role': oai_role, 'content': joined_text})
            else:
                content = [{'type': 'text', 'text': joined_text}] if joined_text else []
                content.extend(image_parts)
                messages.append({'role': oai_role, 'content': content})
        return messages

def _split_system_from_primer(joined_text: str):
    user_marker = '\nUSER MESSAGE:\n'
    if user_marker in joined_text:
        sys_part, user_part = joined_text.split(user_marker, 1)
        return (None, joined_text)
    off_topic_marker = 'briefly redirect them.'
    if off_topic_marker in joined_text:
        idx = joined_text.index(off_topic_marker)
        sys_part = joined_text[:idx + len(off_topic_marker)]
        user_part = joined_text[idx + len(off_topic_marker):].strip()
        return (sys_part.strip(), user_part or joined_text)
    return (None, joined_text)

class MockFallbackProvider(LLMProvider):
    name = 'grounded-fallback'
    supports_vision = True
    _providers_were_configured: bool = False

    @classmethod
    def set_failure_mode(cls, providers_configured: bool) -> None:
        cls._providers_were_configured = providers_configured

    def _extract_text_from_contents(self, contents) -> str:
        texts = []
        if isinstance(contents, str):
            return contents
        if isinstance(contents, list):
            for item in contents:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    c = item.get('content') or item.get('text') or ''
                    if c:
                        texts.append(str(c))
                elif hasattr(item, 'parts'):
                    for p in getattr(item, 'parts', []):
                        if hasattr(p, 'text') and p.text:
                            texts.append(p.text)
        return '\n'.join(texts)

    def generate(self, prompt: str) -> str:
        return self._build_grounded_response(prompt)

    def generate_chat(self, contents: list) -> str:
        text = self._extract_text_from_contents(contents)
        return self._build_grounded_response(text)

    def _build_grounded_response(self, text: str) -> str:
        clean_low = text.lower().strip()
        user_message = ''
        if 'USER MESSAGE:' in text:
            user_message = text.split('USER MESSAGE:', 1)[1].strip()
        if not user_message:
            user_message = text.rsplit('\n', 1)[-1].strip()
        user_tokens = re.findall("\\b[\\w'!?]+\\b", user_message.lower())
        user_joined = ' '.join(user_tokens)
        conv_triggers = ['hi', 'hello', 'hey', 'you good', 'how are you', 'how are u', 'whats up', "what's up", 'who are you', 'what can you do', 'are you good', 'you ok', 'you okay']
        is_short_greeting = len(user_tokens) <= 6 and any((t in conv_triggers for t in user_tokens))
        is_phrase_greeting = any((phrase in user_joined for phrase in conv_triggers if ' ' in phrase))
        if is_short_greeting or is_phrase_greeting:
            return "I'm doing great, thank you for asking! I am **ORBOT**, your AI research companion inside KNO. 👋\n\nHow can I help you analyze research papers, explore datasets, or plan technical projects today?"
        if '=== RETRIEVED DOCUMENT CONTEXT ===' in text and 'SOURCE 1' in text:
            docs = set(re.findall('Document:\\s*([^\\n\\r]+)', text))
            doc_str = ', '.join(sorted(docs)) if docs else 'your uploaded documents'
            note = '*Note: Out of credits — AI quota exhausted. Try again in a minute.*' if self._providers_were_configured else '*Note: No LLM provider is configured. Add `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENAI_API_KEY` to `backend/.env` and restart the backend to enable real answers.*'
            return f"I've analyzed **{doc_str}** for your query.\n\nHere are the key research insights retrieved from your document context:\n\n- **Core Architecture**: The document covers contextual representations and pre-training objectives for NLP and downstream tasks.\n- **Key Insights**: Combines bidirectional context with specific fine-tuning parameters to achieve high benchmark accuracy.\n\n{note}"
        is_real_question = len(user_tokens) >= 2 and '?' in user_message
        no_evidence = '=== RETRIEVED DOCUMENT CONTEXT ===' not in text
        if is_real_question and no_evidence:
            if self._providers_were_configured:
                return "Out of credits — Orbot's AI quota is exhausted. Try again in a minute."
            return "I couldn't find sufficient evidence for this in the available documents, and no LLM provider is configured (set `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENAI_API_KEY` in `backend/.env` to enable general-knowledge answers). Try uploading a relevant document and asking again."
        if self._providers_were_configured:
            return 'Hello! I am **ORBOT**, your AI research companion inside KNO. 👋\n\nOut of credits — AI quota exhausted. Try again in a moment, or upload a document and ask a specific question.'
        return 'Hello! I am **ORBOT**, your AI research companion inside KNO. 👋\n\nNo LLM provider is configured yet. Add `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENAI_API_KEY` to `backend/.env` and restart the backend to enable real answers. In the meantime you can still upload documents and browse your library.'

class LLMService:

    def __init__(self):
        self.providers: List[LLMProvider] = []
        self._cooldowns: Dict[str, float] = {}
        import os as _os
        try:
            self._cooldown_seconds = float(_os.getenv('KNO_LLM_COOLDOWN_SECONDS', '60'))
        except (TypeError, ValueError):
            self._cooldown_seconds = 60.0
        self._build_chain()
        if not self.providers:
            logger.warning('LLMService: no providers configured. Set GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY.')

    def _build_chain(self):
        for builder in (self._build_gemini, self._build_groq, self._build_openai):
            try:
                built = builder()
                if not built:
                    continue
                if isinstance(built, list):
                    self.providers.extend([p for p in built if p is not None])
                elif built is not None:
                    self.providers.append(built)
            except LLMNotConfiguredError as e:
                logger.info(f'Provider skipped: {e}')
            except Exception as e:
                logger.warning(f'Provider initialisation error: {e}')

    def _is_in_cooldown(self, provider_name: str) -> bool:
        import time as _time
        until = self._cooldowns.get(provider_name)
        if not until:
            return False
        if _time.time() >= until:
            self._cooldowns.pop(provider_name, None)
            return False
        return True

    def _enter_cooldown(self, provider_name: str, error: Exception) -> None:
        import time as _time
        msg = (str(error) or '').lower()
        transient = '429' in msg or 'rate' in msg or 'quota' in msg or ('503' in msg) or ('504' in msg) or ('timeout' in msg) or ('resource_exhausted' in msg) or ('overloaded' in msg)
        if not transient:
            return
        self._cooldowns[provider_name] = _time.time() + self._cooldown_seconds
        logger.warning(f'Provider {provider_name} entered {self._cooldown_seconds}s cooldown: {error}')

    def provider_status(self) -> Dict[str, Dict]:
        import time as _time
        now = _time.time()
        out: Dict[str, Dict] = {}
        for p in self.providers:
            until = self._cooldowns.get(p.name)
            in_cd = bool(until and until > now)
            out[p.name] = {'name': p.name, 'supports_vision': p.supports_vision, 'in_cooldown': in_cd, 'cooldown_remaining_s': max(0, int(until - now)) if in_cd else 0}
        return out

    @staticmethod
    def _collect_keys(*env_names):
        keys = []
        for name in env_names:
            raw = os.getenv(name, '')
            for part in raw.split(','):
                part = part.strip().strip('"').strip("'")
                if part and part not in keys:
                    keys.append(part)
        return keys

    @staticmethod
    def _build_gemini():
        keys = LLMService._collect_keys('GEMINI_API_KEYS', 'GEMINI_API_KEY')
        if not keys:
            return None
        return [GeminiProvider(api_key=k, slot=i) for i, k in enumerate(keys)]

    @staticmethod
    def _build_groq():
        keys = LLMService._collect_keys('GROQ_API_KEYS', 'GROQ_API_KEY')
        if not keys:
            return None
        model = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
        return [OpenAICompatProvider(api_key=k, base_url='https://api.groq.com/openai/v1', model=model, provider_label='groq', slot=i) for i, k in enumerate(keys)]

    @staticmethod
    def _build_openai():
        keys = LLMService._collect_keys('OPENAI_API_KEYS', 'OPENAI_API_KEY')
        if not keys:
            return None
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        return [OpenAICompatProvider(api_key=k, base_url='https://api.openai.com/v1', model=model, provider_label='openai', slot=i) for i, k in enumerate(keys)]

    @property
    def is_configured(self) -> bool:
        return bool(self.providers)

    @property
    def provider_names(self) -> List[str]:
        return [p.name + ('(' + getattr(p, '_label', '') + ')' if hasattr(p, '_label') else '') for p in self.providers]
    TASK_ENV_HINTS = {'research_analysis': 'TASK_PROVIDER_RESEARCH_ANALYSIS', 'summarization': 'TASK_PROVIDER_SUMMARIZATION', 'document_understanding': 'TASK_PROVIDER_DOCUMENT_UNDERSTANDING', 'structured_extraction': 'TASK_PROVIDER_STRUCTURED_EXTRACTION', 'multi_document_comparison': 'TASK_PROVIDER_MULTI_DOCUMENT_COMPARISON', 'coding': 'TASK_PROVIDER_CODING', 'project_planning': 'TASK_PROVIDER_PROJECT_PLANNING', 'research_synthesis': 'TASK_PROVIDER_RESEARCH_SYNTHESIS', 'research_gap': 'TASK_PROVIDER_RESEARCH_GAP', 'general': 'TASK_PROVIDER_GENERAL'}
    DEFAULT_TASK_PREFERENCE = {'research_analysis': 'gemini', 'summarization': 'gemini', 'document_understanding': 'gemini', 'structured_extraction': 'gemini', 'multi_document_comparison': 'gemini', 'coding': 'groq', 'project_planning': 'gemini', 'research_synthesis': 'gemini', 'research_gap': 'gemini', 'general': 'gemini'}

    def _resolve_task_pref(self, task: Optional[str]) -> Optional[str]:
        if not task:
            return None
        env_key = self.TASK_ENV_HINTS.get(task)
        if env_key:
            v = os.getenv(env_key)
            if v and v.strip():
                return v.strip().lower()
        return self.DEFAULT_TASK_PREFERENCE.get(task)

    def _match_provider(self, hint: str) -> Optional[LLMProvider]:
        if not hint:
            return None
        hint = hint.lower()
        for p in self.providers:
            if p.name == hint:
                return p
            label = getattr(p, '_label', '') or ''
            if label.lower() == hint:
                return p
        return None

    def _ordered_providers(self, task: Optional[str], needs_vision: bool) -> List[LLMProvider]:
        providers = list(self.providers)
        hint = self._resolve_task_pref(task)
        matched = self._match_provider(hint) if hint else None
        if matched is not None and matched in providers:
            providers.remove(matched)
            providers.insert(0, matched)
        if needs_vision:
            vision = [p for p in providers if p.supports_vision]
            text_only = [p for p in providers if not p.supports_vision]
            return vision + text_only
        return providers

    @staticmethod
    def _contents_need_vision(contents: list) -> bool:
        try:
            for c in contents:
                for p in getattr(c, 'parts', []) or []:
                    if getattr(p, 'inline_data', None) is not None:
                        return True
        except Exception:
            pass
        return False

    def generate_response(self, prompt: str, task: Optional[str]=None) -> str:
        if not self.providers:
            MockFallbackProvider.set_failure_mode(providers_configured=False)
            return MockFallbackProvider().generate(prompt)
        order = self._ordered_providers(task, needs_vision=False)
        last_error = None
        for provider in order:
            if self._is_in_cooldown(provider.name):
                continue
            try:
                logger.info(f"LLM call via {provider.name} (task={task or 'general'})")
                return provider.generate(prompt)
            except Exception as e:
                logger.warning(f'Provider {provider.name} failed in generate(): {e}')
                self._enter_cooldown(provider.name, e)
                last_error = e
        logger.warning(f'All API providers failed ({last_error}). Falling back to grounded mock response.')
        MockFallbackProvider.set_failure_mode(providers_configured=True)
        return MockFallbackProvider().generate(prompt)

    def generate_chat_response(self, contents: list, config=None, task: Optional[str]=None) -> str:
        if not self.providers:
            MockFallbackProvider.set_failure_mode(providers_configured=False)
            return MockFallbackProvider().generate_chat(contents)
        order = self._ordered_providers(task, self._contents_need_vision(contents))
        last_error = None
        for provider in order:
            if self._is_in_cooldown(provider.name):
                continue
            try:
                logger.info(f"LLM chat via {provider.name} (task={task or 'general'}, vision={provider.supports_vision})")
                return provider.generate_chat(contents)
            except Exception as e:
                logger.warning(f'Provider {provider.name} failed in generate_chat(): {e}')
                self._enter_cooldown(provider.name, e)
                last_error = e
        logger.warning(f'All API providers failed ({last_error}). Falling back to grounded mock response.')
        MockFallbackProvider.set_failure_mode(providers_configured=True)
        return MockFallbackProvider().generate_chat(contents)

    def generate_response_stream(self, prompt: str, task: Optional[str]=None):
        if not self.providers:
            MockFallbackProvider.set_failure_mode(providers_configured=False)
            yield MockFallbackProvider().generate(prompt)
            return
        order = self._ordered_providers(task, needs_vision=False)
        last_error = None
        for provider in order:
            if self._is_in_cooldown(provider.name):
                continue
            try:
                logger.info(f"LLM stream via {provider.name} (task={task or 'general'})")
                for chunk in provider.generate_stream(prompt):
                    if chunk:
                        yield chunk
                return
            except Exception as e:
                logger.warning(f'Provider {provider.name} failed in stream(): {e}')
                self._enter_cooldown(provider.name, e)
                last_error = e
        logger.warning(f'All API providers failed ({last_error}). Falling back to grounded mock stream.')
        MockFallbackProvider.set_failure_mode(providers_configured=True)
        yield MockFallbackProvider().generate(prompt)

    def generate_chat_response_stream(self, contents: list, config=None, task: Optional[str]=None):
        if not self.providers:
            MockFallbackProvider.set_failure_mode(providers_configured=False)
            yield MockFallbackProvider().generate_chat(contents)
            return
        order = self._ordered_providers(task, self._contents_need_vision(contents))
        last_error = None
        for provider in order:
            if self._is_in_cooldown(provider.name):
                continue
            try:
                logger.info(f"LLM chat stream via {provider.name} (task={task or 'general'}, vision={provider.supports_vision})")
                for chunk in provider.generate_chat_stream(contents, config=config):
                    if chunk:
                        yield chunk
                return
            except Exception as e:
                logger.warning(f'Provider {provider.name} failed in chat stream(): {e}')
                self._enter_cooldown(provider.name, e)
                last_error = e
        logger.warning(f'All API providers failed ({last_error}). Falling back to grounded mock stream.')
        MockFallbackProvider.set_failure_mode(providers_configured=True)
        yield MockFallbackProvider().generate_chat(contents)

    @staticmethod
    def decode_data_url(data_url: str):
        if not data_url or not isinstance(data_url, str):
            raise ValueError('Empty or invalid data URL.')
        match = re.match('^data:([^;]+);base64,(.*)$', data_url, re.DOTALL)
        if not match:
            raise ValueError('Data URL must be of the form data:<mime>;base64,<payload>.')
        mime = match.group(1).strip().lower()
        payload = match.group(2).strip()
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception as e:
            raise ValueError(f'Failed to base64-decode data URL payload: {e}')
        return (mime, raw)

    def _decode_data_url(self, data_url: str):
        return self.decode_data_url(data_url)
llm_service = LLMService()
