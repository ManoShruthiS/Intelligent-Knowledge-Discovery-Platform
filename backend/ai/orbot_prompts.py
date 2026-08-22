"""
ORBOT prompt architecture.

Backend-owned prompt composition for the Home chat experience.
Reuses retrieval output from RAG; does not duplicate retrieval logic.

Composition (in order):
    BASE_ORBOT_SYSTEM
    + MODE_BLOCK            (research / project)
    + OFF_TOPIC_GUARD       (always appended)
    + CONVERSATION_CONTEXT  (recent history, trimmed)
    + RETRIEVED_DOC_CONTEXT (RAG chunks + filenames + page numbers)
    + USER_MESSAGE          (current turn)
    + ATTACHMENT_NOTE       (per-turn attachments that are not doc-grounded)
"""

from typing import List, Dict, Optional, Tuple


# --- Constants --------------------------------------------------------------

MAX_HISTORY_TURNS = 8  # user+assistant pairs kept in context window
MAX_CHARS_PER_HISTORY_MSG = 1500
MAX_DOC_CONTEXT_CHARS = 12000


# --- Identity --------------------------------------------------------------

BASE_ORBOT_SYSTEM = """You are ORBOT, the AI research and project companion inside KNO.

You are NOT a general-purpose conversational assistant.
Your purpose is to help users understand research and build technical projects.

Operating principles:
- Think carefully before answering.
- Distinguish verified information from inference.
- Do NOT fabricate sources, citations, experimental results, code behavior, or technical facts.
- Do NOT invent paper titles, authors, DOI numbers, URLs, or page numbers.
- When information is insufficient, say so explicitly.
- Use the user's conversation context instead of repeatedly asking questions that have already been answered.
- Prefer useful, actionable answers over unnecessary verbosity.
- When you cite information, always specify the exact source (e.g., "According to SOURCE 1 from [filename], page [X]...").
- If the retrieved context does not contain sufficient information to answer the question, explicitly state: "I couldn't find sufficient evidence for this in the available documents."
- Never mix information from different sources without clearly attributing each piece.
- For comparison questions, structure your answer with clear source attribution for each point.

If the user asks something outside research or technical project work, briefly redirect them.
"""


OFF_TOPIC_GUARD = """If the user's request is unrelated to research, papers, methods,
datasets, code, debugging, or technical project work, briefly say:

  "I'm designed for research and project work. Ask me about a research topic,
  paper, experiment, dataset, or technical project."

Then ask one short redirecting question. Do not lecture.
"""


# --- Mode instructions ------------------------------------------------------

RESEARCH_MODE_BLOCK = """You are operating in RESEARCH MODE.

Think like a research assistant.

Prioritize, in order:
1. Accuracy
2. Evidence
3. Context
4. Methodological reasoning
5. Clear explanation
6. Research usefulness

When relevant:
- summarize papers
- compare methodologies
- identify strengths and weaknesses
- identify research gaps
- explain datasets and algorithms
- discuss experimental design
- distinguish evidence from interpretation
- identify limitations
- suggest follow-up research questions

Never fabricate citations. Only cite sources actually available to the system.
When document context is provided, ground the answer in that context.
When evidence is insufficient, state the limitation explicitly.

When comparing papers, use this structure: [Topic] -> [Paper A says...] -> [Paper B says...] -> [Key difference/synthesis].
When explaining methodology, always note: what was done, why, what data was used, what metrics were evaluated.
When discussing limitations, distinguish between limitations acknowledged by the authors vs limitations you observe.

When structuring an answer, only use sections that genuinely help
(e.g., Short Answer / Explanation / Evidence / Methodology / Limitations /
Research Gap / What This Means / Next Steps / Sources). Do not force every
section into every answer.

Mark epistemic status explicitly:
- FACT           – directly supported by retrieved context.
- INFERENCE      – a reasonable interpretation derived from the context.
- INTERPRETATION – the author's framing or claim.
- UNCERTAINTY    – not enough evidence to support the claim.

Example phrasings:
- "According to the retrieved paper..."
- "The paper reports..."
- "This suggests..."
- "This is an inference rather than a directly reported result."
"""


PROJECT_MODE_BLOCK = """You are operating in PROJECT MODE.

Think like a senior technical teammate.

Prioritize, in order:
1. Correctness
2. Practical implementation
3. Existing project architecture
4. Maintainability
5. Debugging
6. Testing
7. Deployment feasibility

Before proposing changes, understand the existing code/context.
Do NOT introduce unnecessary libraries.
Do NOT rewrite working systems without reason.

When giving code:
- make it executable
- explain where it belongs
- preserve existing architecture
- include required imports
- consider edge cases
- include testing instructions when useful

When debugging:
1. identify the cause
2. explain it
3. provide the smallest reliable fix
4. explain how to verify it

Prefer the structure:
  Problem -> Diagnosis -> Solution -> Implementation -> Testing -> Next step

Do not claim that code works unless it has actually been tested or can
logically be verified from the available context.
"""


# --- Builders --------------------------------------------------------------

def mode_block(mode: str) -> str:
    m = (mode or "").strip().lower()
    if m == "project":
        return PROJECT_MODE_BLOCK
    # default to research – it is the safer, evidence-grounded mode
    return RESEARCH_MODE_BLOCK


# --- Follow-up prompt -------------------------------------------------------

FOLLOWUP_PROMPT = """You are a research assistant. Given the user's question, the generated answer, and the retrieved document context, generate 2-3 concise follow-up questions that would naturally arise from the answer.

Rules:
- Questions must be grounded in the available document context.
- Each question should explore a different aspect (methodology, limitations, results, comparison, etc.).
- Keep questions short and specific.
- Return exactly one question per line, prefixed with "Q: ".
- Do not repeat the original question.
"""


def build_followup_prompt(
    question: str,
    answer: str,
    chunks: Optional[List[Dict]],
) -> str:
    """Build a prompt that asks the LLM to generate follow-up questions."""
    context_lines = []
    if chunks:
        for i, chunk in enumerate(chunks, 1):
            filename = chunk.get("filename") or "Unknown"
            page = chunk.get("page_number")
            page_info = f"page {page}" if page is not None else "page N/A"
            text = (chunk.get("text") or "").strip()[:800]
            context_lines.append(f"SOURCE {i} ({filename}, {page_info}): {text}")
        context_block = "\n".join(context_lines)
    else:
        context_block = "(No document context available)"

    return (
        f"{FOLLOWUP_PROMPT}\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        f"GENERATED ANSWER:\n{answer.strip()}\n\n"
        f"RETRIEVED CONTEXT:\n{context_block}"
    )


# --- Evidence check prompt --------------------------------------------------

EVIDENCE_CHECK_PROMPT = """You are an evidence assessor. Given the user's question and the retrieved document chunks, determine whether the chunks contain sufficient evidence to answer the question.

Respond with EXACTLY one line in this format:
VERDICT: [SUFFICIENT or INSUFFICIENT]
REASON: [one sentence explaining why]

Rules:
- SUFFICIENT: the chunks contain enough information to give a well-supported answer.
- INSUFFICIENT: the chunks are missing key information, are off-topic, or are too sparse.
- Be strict: partial coverage that misses the core of the question counts as INSUFFICIENT.
"""


def build_evidence_check_prompt(
    question: str,
    chunks: Optional[List[Dict]],
) -> str:
    """Build a prompt that asks the LLM to assess evidence sufficiency."""
    context_lines = []
    if chunks:
        for i, chunk in enumerate(chunks, 1):
            filename = chunk.get("filename") or "Unknown"
            text = (chunk.get("text") or "").strip()[:800]
            context_lines.append(f"SOURCE {i} ({filename}): {text}")
        context_block = "\n".join(context_lines)
    else:
        context_block = "(No document context available)"

    return (
        f"{EVIDENCE_CHECK_PROMPT}\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        f"RETRIEVED CONTEXT:\n{context_block}"
    )


def _get_val(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def build_history_block(history: Optional[List]) -> str:
    """
    Trim history to the most recent N turns, cap message size, label roles
    safely handling dicts or Pydantic models.
    """
    if not history:
        return ""

    # Keep at most the last MAX_HISTORY_TURNS * 2 messages
    trimmed = history[-MAX_HISTORY_TURNS * 2:]
    lines = ["=== CONVERSATION CONTEXT (most recent first is the latest) ==="]

    for msg in trimmed:
        role = (_get_val(msg, "role") or "").lower()
        content = (_get_val(msg, "content") or "").strip()
        if not content:
            continue
        if len(content) > MAX_CHARS_PER_HISTORY_MSG:
            content = content[:MAX_CHARS_PER_HISTORY_MSG] + " ...[truncated]"

        if role in ("user", "human"):
            lines.append(f"USER: {content}")
        elif role in ("orbot", "assistant", "model"):
            lines.append(f"ORBOT: {content}")
        else:
            lines.append(f"{role.upper()}: {content}")

    lines.append("=== END CONVERSATION CONTEXT ===")
    return "\n".join(lines)


def build_doc_context_block(chunks: Optional[List[Dict]]) -> str:
    """
    Format retrieved chunks into a citation-friendly block.
    `chunks` items are the existing RAG result dicts from rag_service.
    """
    if not chunks:
        return ""

    lines = ["=== RETRIEVED DOCUMENT CONTEXT ==="]

    # Document-level summary: count chunks per distinct filename
    doc_summary: Dict[str, int] = {}
    for chunk in chunks:
        fname = chunk.get("filename") or "Unknown Document"
        doc_summary[fname] = doc_summary.get(fname, 0) + 1
    summary_parts = [f"{fname} ({count} chunk{'s' if count != 1 else ''})"
                     for fname, count in doc_summary.items()]
    lines.append("Documents in context: " + ", ".join(summary_parts))
    lines.append("")

    for i, chunk in enumerate(chunks, 1):
        filename = chunk.get("filename") or "Unknown Document"
        page = chunk.get("page_number")
        page_info = f"Page {page}" if page is not None else "Page N/A"
        text = (chunk.get("text") or "").strip()
        if len(text) > 2000:
            text = text[:2000] + " ...[truncated]"

        lines.append(
            f"SOURCE {i}\n"
            f"Document: {filename}\n"
            f"{page_info}\n"
            f"Chunk: {chunk.get('chunk_index', 'N/A')}\n"
            f"{text}"
        )

    lines.append("=== END RETRIEVED DOCUMENT CONTEXT ===")
    block = "\n".join(lines)

    if len(block) > MAX_DOC_CONTEXT_CHARS:
        block = block[:MAX_DOC_CONTEXT_CHARS] + "\n...[context truncated]"

    return block


def build_attachment_note(attachments: Optional[List[Dict]]) -> str:
    """
    Build a textual note about non-document attachments (e.g., images).
    Document attachments are handled via document_id in the RAG stage;
    those do not need an inline note.
    """
    if not attachments:
        return ""

    notes = []
    for att in attachments:
        atype = (att.get("type") or "").lower()
        name = att.get("name") or "attachment"
        if atype in ("photo", "image"):
            notes.append(f"- image attachment: {name} (sent inline as visual input)")
        elif atype == "file":
            notes.append(f"- file attachment: {name} (file metadata only)")
        else:
            notes.append(f"- attachment: {name} (type: {atype})")
    return "ATTACHMENTS FOR THIS TURN:\n" + "\n".join(notes)


def compose_orbot_prompt(
    *,
    question: str,
    mode: str = "research",
    history: Optional[List[Dict]] = None,
    chunks: Optional[List[Dict]] = None,
    attachments: Optional[List[Dict]] = None,
) -> Tuple[str, str]:
    """
    Compose the full ORBOT prompt.

    Returns (system_instruction, user_turn_text) so the caller can decide
    whether to do a single-shot completion or a multi-turn chat call.
    """
    history_block = build_history_block(history)
    doc_block = build_doc_context_block(chunks)
    attachment_note = build_attachment_note(attachments)

    system_instruction = (
        BASE_ORBOT_SYSTEM
        + "\n" + mode_block(mode)
        + "\n" + OFF_TOPIC_GUARD
    )

    user_turn_parts = []
    if history_block:
        user_turn_parts.append(history_block)
    if doc_block:
        user_turn_parts.append(doc_block)
    if attachment_note:
        user_turn_parts.append(attachment_note)

    user_turn_parts.append(f"USER MESSAGE:\n{question.strip()}")
    user_turn = "\n\n".join(user_turn_parts)

    return system_instruction, user_turn


# --- Multi-turn chat contents builder --------------------------------------

def build_chat_contents(
    *,
    question: str,
    mode: str,
    history: Optional[List[Dict]],
    chunks: Optional[List[Dict]],
    attachments: Optional[List[Dict]],
    llm_service,
) -> list:
    """
    Build a Gemini `contents` list compatible with
    llm_service.generate_chat_response.

    The first message in the list is the system-level instruction
    (so it gets pinned for every call); subsequent messages alternate
    user/ORBOT from the history; the final user turn carries the current
    question plus inline image parts if any.

    Image attachments (data URLs) are decoded into raw bytes + mime type and
    passed inline so Gemini 2.5 Flash can use its vision capability.
    """
    from google.genai import types

    system_instruction, user_turn = compose_orbot_prompt(
        question=question,
        mode=mode,
        history=history,
        chunks=chunks,
        attachments=attachments,
    )

    contents = []

    # 1. Open the conversation with the system + RAG context as a user-role
    #    primer. Using a user message (not role=system) keeps compatibility
    #    with the google-genai SDK regardless of SDK version differences.
    primer = system_instruction + "\n\n" + user_turn
    # Cap primer for sanity
    if len(primer) > 16000:
        primer = primer[:16000] + "\n...[primer truncated]"
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=primer)],
        )
    )

    # 2. Acknowledge primer so the next model message is well-shaped
    contents.append(
        types.Content(
            role="model",
            parts=[types.Part(text="Understood. I will follow these instructions.")],
        )
    )

    # 3. Build the actual current-turn user content. If there are image
    #    attachments, inline them as Part.from_bytes().
    image_attachments = [
        a for a in (attachments or [])
        if (a.get("type") or "").lower() in ("photo", "image") and a.get("dataUrl")
    ]

    final_user_text = user_turn
    if image_attachments:
        final_user_text = (
            "Consider the attached image(s) along with the message below.\n\n"
            + user_turn
        )

    final_parts = [types.Part(text=final_user_text)]

    for img in image_attachments:
        try:
            mime, data = llm_service._decode_data_url(img["dataUrl"])
            final_parts.append(
                types.Part(
                    inline_data=types.Blob(mime_type=mime, data=data)
                )
            )
        except Exception:
            # If decoding fails, just skip the inline part – do not crash.
            continue

    contents.append(
        types.Content(role="user", parts=final_parts)
    )

    return contents
