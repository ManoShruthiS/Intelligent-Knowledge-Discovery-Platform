"""
Research Studio service for KNO.

Provides:
  - Paper templates (IEEE, conference, journal, literature review,
    project report, thesis/dissertation) with sensible skeletons
  - Studio document CRUD backed by `studio_documents` table
  - ORBOT-assisted academic rewrite / clarity / structure help
"""

import logging
from typing import Dict, List

import database.database as db
from ai.llm_service import llm_service

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------------

TEMPLATES = {
    "ieee": {
        "name": "IEEE Conference Paper",
        "description": "Abstract, Index Terms, Introduction, Related Work, "
                       "Methodology, Results, Discussion, Conclusion, References.",
        "skeleton": """# {title}

## Authors
{authors}

## Abstract
Provide a 150–250 word abstract: problem, method, key result, significance.

## Index Terms
- term 1
- term 2

## I. Introduction
Describe the problem, why it matters, and the paper's contribution.

## II. Related Work
Compare with prior approaches. Identify gaps.

## III. Methodology
Detail the approach, datasets, evaluation protocol.

## IV. Results
Present quantitative results. Use tables/figures.

## V. Discussion
Interpret results. Discuss limitations.

## VI. Conclusion
Summarize the contribution and future work.

## References
1. ...
""",
    },
    "conference": {
        "name": "Conference Paper (Generic)",
        "description": "Standard scientific conference template.",
        "skeleton": """# {title}

## Abstract
150–250 words.

## 1. Introduction

## 2. Background

## 3. Method

## 4. Results

## 5. Discussion

## 6. Conclusion

## Acknowledgments
(optional)

## References
""",
    },
    "journal": {
        "name": "Journal Article",
        "description": "Extended structure suitable for a peer-reviewed journal.",
        "skeleton": """# {title}

## Abstract

## 1. Introduction
## 2. Related Work
## 3. Materials and Methods
## 4. Results
## 5. Discussion
## 6. Conclusions
## Acknowledgments
## Author Contributions
## Conflicts of Interest
## References
## Supplementary Materials (optional)
""",
    },
    "literature_review": {
        "name": "Literature Review",
        "description": "Theme-by-theme synthesis of multiple papers.",
        "skeleton": """# Literature Review: {title}

## 1. Introduction
Scope, methodology of the search.

## 2. Background

## 3. Themes
### 3.1 Theme A
### 3.2 Theme B
### 3.3 Theme C

## 4. Gaps and Open Questions

## 5. Conclusion

## References
""",
    },
    "project_report": {
        "name": "Project Report",
        "description": "Final-year capstone-style project report.",
        "skeleton": """# {title}

## Abstract

## 1. Introduction
## 2. Problem Statement
## 3. Objectives
## 4. Literature Survey
## 5. Methodology
## 6. System Design / Architecture
## 7. Implementation
## 8. Results and Discussion
## 9. Conclusion and Future Work
## References
## Appendices
""",
    },
    "thesis": {
        "name": "Thesis / Dissertation",
        "description": "Long-form dissertation with chapters.",
        "skeleton": """# {title}

## Abstract

## Acknowledgments

## Table of Contents

## Chapter 1: Introduction
## Chapter 2: Literature Review
## Chapter 3: Methodology
## Chapter 4: Results
## Chapter 5: Discussion
## Chapter 6: Conclusion

## References

## Appendices
""",
    },
}


def list_templates() -> List[Dict]:
    return [
        {"key": k, "name": v["name"], "description": v["description"]}
        for k, v in TEMPLATES.items()
    ]


def render_skeleton(template_key: str, title: str = "Untitled") -> str:
    tpl = TEMPLATES.get((template_key or "").lower())
    if not tpl:
        tpl = TEMPLATES["ieee"]
    return tpl["skeleton"].format(title=title or "Untitled")


# ----------------------------------------------------------------------------
# Studio documents
# ----------------------------------------------------------------------------

class StudioService:
    def list(self, workspace_id: str) -> List[dict]:
        return db.list_studio_docs(workspace_id)

    def create(self, workspace_id: str, template: str, title: str) -> dict:
        tpl = (template or "ieee").lower()
        if tpl not in TEMPLATES:
            tpl = "ieee"
        title = (title or "Untitled").strip()[:200]
        content = render_skeleton(tpl, title)
        return db.create_studio_doc(workspace_id, tpl, title, content)

    def get(self, sid: str) -> dict | None:
        return db.get_studio_doc(sid)

    def update(self, sid: str, **fields) -> dict | None:
        return db.update_studio_doc(sid, **fields)

    def delete(self, sid: str) -> bool:
        return db.delete_studio_doc(sid)

    def help_action(self, sid: str, action: str, instruction: str = "") -> dict:
        """
        ORBOT-assisted academic help.
        action: 'rewrite' | 'clarify' | 'structure' | 'find_unsupported' | 'insert_citation_placeholder'
        """
        doc = db.get_studio_doc(sid)
        if not doc:
            raise ValueError("Studio document not found.")
        prompt = _STUDIO_HELP_PROMPT.format(
            action=action,
            title=doc.get("title", ""),
            template=doc.get("template", ""),
            content=doc.get("content", "")[:12000],
            instruction=(instruction or "").strip(),
        )
        try:
            raw = llm_service.generate_response(prompt, task="document_understanding")
        except Exception as e:
            logger.warning(f"Studio help failed: {e}")
            raw = ""
        return {"action": action, "output": (raw or "").strip()}


_STUDIO_HELP_PROMPT = """You are ORBOT in STUDIO MODE for academic writing.

The user has a paper draft:

Title: {title}
Template: {template}

---
CURRENT CONTENT:
{content}
---

User instruction: {instruction}

Task: perform the requested action on the CURRENT CONTENT.

Possible actions:
- rewrite: rewrite the section for academic tone
- clarify: improve clarity without changing meaning
- structure: suggest better section structure
- find_unsupported: list claims that look unsupported by the supplied content
- insert_citation_placeholder: insert [CITE: ...] placeholders where citations should appear

Output:
- Markdown text that the user can paste back into their draft.
- Be specific to the content above; do not give generic advice.
- Never invent bibliographic facts.
- Keep changes consistent with the existing template.

Now perform the action: {action}
"""


studio_service = StudioService()
