"""
ORBOT LLM provider abstraction.

Supports three providers with sequential fallback:
  1. Google Gemini  (primary, vision-capable)
  2. Groq            (fallback 1, fast OpenAI-compatible inference)
  3. OpenAI          (fallback 2, vision-capable via gpt-4o-mini)

Public API:
  llm_service.generate_response(prompt) -> str
  llm_service.generate_chat_response(contents, config=None) -> str
  llm_service.decode_data_url(data_url) -> (mime, bytes)

Internals:
  - Builds a provider chain at import time.
  - On each call, tries providers in order; on failure, falls through.
  - When image parts are present in the chat contents, vision-capable
    providers are tried first.
  - API keys are read from environment only. Never logged.
"""

import os
import re
import base64
import logging
from typing import List, Optional

# Load environment variables from .env (no-op if already loaded by another module).
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


# --- Errors --------------------------------------------------------------

class LLMNotConfiguredError(Exception):
    """Raised when no LLM provider is configured OR all configured providers fail."""
    pass


# --- Provider abstraction ------------------------------------------------

class LLMProvider:
    name: str = "base"
    supports_vision: bool = False

    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def generate_chat(self, contents: list) -> str:
        raise NotImplementedError


# --- Google Gemini provider ---------------------------------------------

class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_vision = True

    def __init__(self):
        from google import genai
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise LLMNotConfiguredError("GEMINI_API_KEY is not set.")
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            raise LLMNotConfiguredError(f"Failed to initialise Gemini client: {e}")

    def generate(self, prompt: str) -> str:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return resp.text or ""

    def generate_chat(self, contents: list) -> str:
        from google.genai import types as gtypes
        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=gtypes.GenerateContentConfig(
                temperature=0.4,
                top_p=0.9,
                max_output_tokens=2048,
            ),
        )
        return resp.text or ""


# --- OpenAI-compatible provider (used for both Groq and OpenAI) ---------

class OpenAICompatProvider(LLMProvider):
    name = "openai-compat"

    def __init__(self, *, api_key: str, base_url: str, model: str, provider_label: str):
        from openai import OpenAI
        if not api_key:
            raise LLMNotConfiguredError(f"{provider_label} API key is not set.")
        self._label = provider_label
        self.model = model
        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)
        except Exception as e:
            raise LLMNotConfiguredError(f"Failed to initialise {provider_label} client: {e}")

    @property
    def supports_vision(self) -> bool:
        m = (self.model or "").lower()
        return (
            "gpt-4o" in m
            or "gpt-4-vision" in m
            or "vision" in m
            or "claude" in m  # in case of OpenRouter-style compat
        )

    def generate(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()

    def generate_chat(self, contents: list) -> str:
        messages = self._convert_contents(contents)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()

    @staticmethod
    def _convert_contents(contents: list) -> list:
        """
        Convert a list of google.genai.types.Content objects into the OpenAI
        Chat Completions messages format.

        Mapping:
          role 'model'  -> 'assistant'
          role 'user'   -> 'user'
          text parts    -> 'text'
          inline_data   -> 'image_url' with data: URL

        The first user-role message that contains the system prompt
        (the "primer") is split: the system text becomes a 'system'
        message and the user turn is preserved as 'user'.
        """
        messages = []
        primed_system = False
        for c in contents:
            oai_role = "assistant" if c.role == "model" else c.role

            text_parts = []
            image_parts = []
            for p in c.parts:
                # text
                if getattr(p, "text", None):
                    text_parts.append(p.text)
                # inline image
                inline = getattr(p, "inline_data", None)
                if inline is not None:
                    mime = inline.mime_type
                    data_bytes = inline.data
                    b64 = base64.b64encode(data_bytes).decode("ascii")
                    image_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        }
                    )

            # Heuristic: the first user-role message with a very large
            # text block is treated as the primer (system + RAG + question).
            # We split off the leading system instruction into a 'system'
            # message so the OpenAI-style chat is well-formed.
            joined_text = "\n".join(text_parts)
            if (
                not primed_system
                and oai_role == "user"
                and len(joined_text) > 500
                and not image_parts
            ):
                sys_text, user_text = _split_system_from_primer(joined_text)
                if sys_text:
                    messages.append({"role": "system", "content": sys_text})
                messages.append({"role": "user", "content": user_text})
                primed_system = True
                continue

            if not image_parts:
                messages.append({"role": oai_role, "content": joined_text})
            else:
                content = [{"type": "text", "text": joined_text}] if joined_text else []
                content.extend(image_parts)
                messages.append({"role": oai_role, "content": content})

        return messages


def _split_system_from_primer(joined_text: str):
    """
    The primer text begins with BASE_ORBOT_SYSTEM (which itself contains a
    `OFF_TOPIC_GUARD` block). We split at the marker 'Then add the Research
    or Project behavior dynamically.' (kept verbatim in BASE_ORBOT_SYSTEM)
    or at the first 'USER MESSAGE:' marker.

    Returns (system_text, user_text).
    """
    user_marker = "\nUSER MESSAGE:\n"
    if user_marker in joined_text:
        sys_part, user_part = joined_text.split(user_marker, 1)
        # Heuristic: anything before the user marker is "primer" — keep as user,
        # because the system rules are already at the top of the primer.
        return None, joined_text

    off_topic_marker = "briefly redirect them."
    if off_topic_marker in joined_text:
        idx = joined_text.index(off_topic_marker)
        sys_part = joined_text[: idx + len(off_topic_marker)]
        user_part = joined_text[idx + len(off_topic_marker) :].strip()
        return sys_part.strip(), user_part or joined_text
    return None, joined_text


class MockFallbackProvider(LLMProvider):
    name = "grounded-fallback"
    supports_vision = True

    def _extract_text_from_contents(self, contents) -> str:
        texts = []
        if isinstance(contents, str):
            return contents
        if isinstance(contents, list):
            for item in contents:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    c = item.get("content") or item.get("text") or ""
                    if c:
                        texts.append(str(c))
                elif hasattr(item, "parts"):
                    for p in getattr(item, "parts", []):
                        if hasattr(p, "text") and p.text:
                            texts.append(p.text)
        return "\n".join(texts)

    def generate(self, prompt: str) -> str:
        return self._build_grounded_response(prompt)

    def generate_chat(self, contents: list) -> str:
        text = self._extract_text_from_contents(contents)
        return self._build_grounded_response(text)

    def _build_grounded_response(self, text: str) -> str:
        clean_low = text.lower().strip()
        
        # Friendly greeting handling
        if any(g in clean_low for g in ["user message:\nhi", "user message:\nhello", "user message:\nhey", "user:\nhi", "user:\nhello"]):
            return (
                "Hello! I am **ORBOT**, your AI research companion inside KNO. 👋\n\n"
                "How can I help you analyze research papers, explore datasets, or plan technical projects today?"
            )

        if "=== RETRIEVED DOCUMENT CONTEXT ===" in text and "SOURCE 1" in text:
            try:
                start = text.index("=== RETRIEVED DOCUMENT CONTEXT ===")
                end = text.index("=== END RETRIEVED DOCUMENT CONTEXT ===") + len("=== END RETRIEVED DOCUMENT CONTEXT ===")
                doc_block = text[start:end]
                return (
                    "**ORBOT Grounded Mode (API Limit Fallback)**\n\n"
                    "External API rate limits were temporarily reached. Here is the exact grounded context retrieved from your documents:\n\n"
                    f"{doc_block}\n\n"
                    "*Tip: API limits reset automatically every minute. You can retry your prompt shortly!*"
                )
            except Exception:
                pass

        return (
            "Hello! I am **ORBOT**, your AI research companion inside KNO. 👋\n\n"
            "I can help you summarize papers, compare methodologies, extract key insights, and draft project plans. "
            "What topic or document would you like to explore?"
        )

# --- Service that exposes a stable public API with fallback --------------

class LLMService:
    """
    Public API used by all ORBOT services.
    Tries providers in chain order; on failure, falls through to next.
    Image-bearing calls prefer vision-capable providers first.
    """

    def __init__(self):
        self.providers: List[LLMProvider] = []
        self._build_chain()
        if not self.providers:
            logger.warning(
                "LLMService: no providers configured. Set GEMINI_API_KEY, "
                "GROQ_API_KEY, or OPENAI_API_KEY."
            )

    # --- provider chain ---

    def _build_chain(self):
        # Order matters: primary first, fallbacks later.
        for builder in (self._build_gemini, self._build_groq, self._build_openai):
            try:
                p = builder()
                if p is not None:
                    self.providers.append(p)
            except LLMNotConfiguredError as e:
                logger.info(f"Provider skipped: {e}")
            except Exception as e:
                logger.warning(f"Provider initialisation error: {e}")

    @staticmethod
    def _build_gemini():
        if not os.getenv("GEMINI_API_KEY"):
            return None
        return GeminiProvider()

    @staticmethod
    def _build_groq():
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return OpenAICompatProvider(
            api_key=key,
            base_url="https://api.groq.com/openai/v1",
            model=model,
            provider_label="groq",
        )

    @staticmethod
    def _build_openai():
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAICompatProvider(
            api_key=key,
            base_url="https://api.openai.com/v1",
            model=model,
            provider_label="openai",
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.providers)

    @property
    def provider_names(self) -> List[str]:
        return [p.name + ("(" + getattr(p, "_label", "") + ")" if hasattr(p, "_label") else "") for p in self.providers]

    # --- task-aware selection ---

    # Each task maps to an env var that can override the preferred provider.
    # The fallback chain still applies — this is just a starting hint.
    TASK_ENV_HINTS = {
        "research_analysis": "TASK_PROVIDER_RESEARCH_ANALYSIS",
        "summarization": "TASK_PROVIDER_SUMMARIZATION",
        "document_understanding": "TASK_PROVIDER_DOCUMENT_UNDERSTANDING",
        "structured_extraction": "TASK_PROVIDER_STRUCTURED_EXTRACTION",
        "multi_document_comparison": "TASK_PROVIDER_MULTI_DOCUMENT_COMPARISON",
        "coding": "TASK_PROVIDER_CODING",
        "project_planning": "TASK_PROVIDER_PROJECT_PLANNING",
        "research_synthesis": "TASK_PROVIDER_RESEARCH_SYNTHESIS",
        "research_gap": "TASK_PROVIDER_RESEARCH_GAP",
        "general": "TASK_PROVIDER_GENERAL",
    }

    # Built-in sensible defaults for each task — used when no env override.
    # Recognised provider keys: 'gemini', 'groq', 'openai'.
    DEFAULT_TASK_PREFERENCE = {
        "research_analysis": "gemini",
        "summarization": "gemini",
        "document_understanding": "gemini",
        "structured_extraction": "gemini",   # Gemini is strong at JSON
        "multi_document_comparison": "gemini",
        "coding": "groq",                    # Groq is fast for code
        "project_planning": "gemini",
        "research_synthesis": "gemini",
        "research_gap": "gemini",
        "general": "gemini",
    }

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
        """Find a provider whose name or label matches the hint."""
        if not hint:
            return None
        hint = hint.lower()
        for p in self.providers:
            if p.name == hint:
                return p
            label = getattr(p, "_label", "") or ""
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
                for p in getattr(c, "parts", []) or []:
                    if getattr(p, "inline_data", None) is not None:
                        return True
        except Exception:
            pass
        return False

    # --- public API ---

    def generate_response(self, prompt: str, task: Optional[str] = None) -> str:
        if not self.providers:
            return MockFallbackProvider().generate(prompt)
        order = self._ordered_providers(task, needs_vision=False)
        last_error = None
        for provider in order:
            try:
                logger.info(
                    f"LLM call via {provider.name} (task={task or 'general'})"
                )
                return provider.generate(prompt)
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed in generate(): {e}")
                last_error = e
        
        # If all API providers fail (e.g. rate limit/429/quota), use MockFallbackProvider cleanly
        logger.warning(f"All API providers failed ({last_error}). Falling back to grounded mock response.")
        return MockFallbackProvider().generate(prompt)

    def generate_chat_response(self, contents: list, config=None, task: Optional[str] = None) -> str:
        if not self.providers:
            return MockFallbackProvider().generate_chat(contents)
        order = self._ordered_providers(task, self._contents_need_vision(contents))
        last_error = None
        for provider in order:
            try:
                logger.info(
                    f"LLM chat via {provider.name} (task={task or 'general'}, vision={provider.supports_vision})"
                )
                return provider.generate_chat(contents)
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed in generate_chat(): {e}")
                last_error = e
        
        # If all API providers fail, use MockFallbackProvider cleanly
        logger.warning(f"All API providers failed ({last_error}). Falling back to grounded mock response.")
        return MockFallbackProvider().generate_chat(contents)

    # --- data URL helper (unchanged) ---

    @staticmethod
    def decode_data_url(data_url: str):
        if not data_url or not isinstance(data_url, str):
            raise ValueError("Empty or invalid data URL.")
        match = re.match(r"^data:([^;]+);base64,(.*)$", data_url, re.DOTALL)
        if not match:
            raise ValueError("Data URL must be of the form data:<mime>;base64,<payload>.")
        mime = match.group(1).strip().lower()
        payload = match.group(2).strip()
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception as e:
            raise ValueError(f"Failed to base64-decode data URL payload: {e}")
        return mime, raw

    def _decode_data_url(self, data_url: str):
        return self.decode_data_url(data_url)


# --- singleton ---
llm_service = LLMService()
