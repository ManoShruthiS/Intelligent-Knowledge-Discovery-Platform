"""
Multi-provider LLM smoke test.

Verifies:
  1. At least one provider is configured (env keys loaded).
  2. Plain text generation works through the chain.
  3. Multi-turn chat (no images) works through the chain.
  4. Image-bearing chat either succeeds via a vision-capable provider
     or falls through gracefully.
  5. JSON-parsable responses work for a small structured prompt.

Does NOT echo API keys. Does NOT print environment variables.
"""

import sys
import os
import json

# Ensure backend is on the path
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ai.llm_service import llm_service, LLMNotConfiguredError


def header(label):
    print(f"\n=== {label} ===")


def main():
    print("ORBOT multi-provider smoke test")
    print(f"Configured providers (in chain order): {len(llm_service.providers)}")
    for i, p in enumerate(llm_service.providers):
        try:
            label = getattr(p, "_label", "")
        except Exception:
            label = ""
        vision = "vision" if p.supports_vision else "text-only"
        print(f"  {i+1}. {p.name} {label} — {vision} ({p.model})")

    if not llm_service.providers:
        print("FAIL: no providers configured")
        sys.exit(1)

    # 1. Plain text completion
    header("Plain text completion")
    try:
        out = llm_service.generate_response(
            "Reply with exactly the text: PONG"
        )
        out = (out or "").strip()
        print(f"  OK: '{out[:80]}'")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {str(e)[:160]}")
        return 1

    # 2. Multi-turn chat (text-only)
    header("Multi-turn chat (text-only)")
    try:
        from google.genai import types as gtypes
        contents = [
            gtypes.Content(role="user", parts=[gtypes.Part(text="You are a helpful assistant. Answer in one short sentence.")]),
            gtypes.Content(role="model", parts=[gtypes.Part(text="Understood. I will answer concisely.")]),
            gtypes.Content(role="user", parts=[gtypes.Part(text="What is 2+2?")]),
        ]
        out = llm_service.generate_chat_response(contents)
        out = (out or "").strip()
        print(f"  OK: '{out[:120]}'")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {str(e)[:160]}")
        return 1

    # 3. JSON-structured response
    header("Structured JSON response")
    try:
        out = llm_service.generate_response(
            'Return a single JSON object: {"pong": true}. Do not include any other text.'
        )
        out = (out or "").strip()
        # Try to parse; tolerate code fences
        s = out
        if s.startswith("```"):
            s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(s)
        assert parsed.get("pong") is True
        print(f"  OK: parsed JSON = {parsed}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {str(e)[:160]}")
        return 1

    # 4. Image-bearing chat — only meaningful if a vision-capable provider exists
    header("Image-bearing chat")
    from google.genai import types as gtypes
    # Tiny 1x1 black PNG
    TINY_PNG = (
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
    )
    contents = [
        gtypes.Content(role="user", parts=[
            gtypes.Part(text="Describe this image in exactly 5 words."),
            gtypes.Part(inline_data=gtypes.Blob(mime_type="image/png", data=TINY_PNG)),
        ]),
    ]
    try:
        out = llm_service.generate_chat_response(contents)
        out = (out or "").strip()
        print(f"  OK: '{out[:120]}'")
    except Exception as e:
        print(f"  WARN (no vision provider worked): {type(e).__name__}: {str(e)[:160]}")

    print("\nALL CORE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())