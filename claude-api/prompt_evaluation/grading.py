"""Graders for the reply task: one code grader + one model grader.

Mirrors the lesson's split of criteria:
  - Format        -> code grader   (cheap, deterministic)
  - Task following -> model grader (needs judgement)
"""

import json
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from reply_prompts import CONTENT_REQUIREMENTS

# Load the key BEFORE creating the client (import order must not matter).
load_dotenv(Path(__file__).parent.parent / ".env")

GRADER_MODEL = "claude-haiku-4-5"
client = Anthropic()


# ------------------------------------------------------------- code grader
_VI_CHARS = re.compile(r"[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]", re.I)


def grade_by_code(output: str, message: str = "") -> dict:
    """Format checks. Score is 1-10 like the model grader so they can be averaged."""
    checks = {
        "max_80_words": len(output.split()) <= 80,
        "no_markdown": not re.search(r"(^|\n)\s*(#{1,6}\s|[-*]\s|\d+\.\s)|\*\*|`", output),
        "not_empty": bool(output.strip()),
        # Crude heuristic (Vietnamese diacritics vs. none), enough for this dataset's
        # English + Vietnamese messages. It caught a bug the model grader missed.
        "language_match": bool(_VI_CHARS.search(output)) == bool(_VI_CHARS.search(message)),
    }
    score = max(1, round(10 * sum(checks.values()) / len(checks)))
    return {"score": score, "checks": checks}


# ------------------------------------------------------------ model grader
GRADER_PROMPT = """You are an expert customer-support quality reviewer. Evaluate this AI-drafted reply.

The reply was written to satisfy these requirements:
{requirements}

Length, markdown and language are verified separately by code. Do NOT evaluate or count
them; judge only the requirements above.

<customer_message>
{task}
</customer_message>

<reply>
{solution}
</reply>

Provide your evaluation as a JSON object with exactly these keys, in this order:
- "strengths": an array of 1-3 key strengths
- "weaknesses": an array of 1-3 key areas for improvement
- "reasoning": a concise explanation of your assessment
- "score": a number from 1 to 10 (10 = fully meets every requirement; deduct for each violated requirement)

Respond with the JSON object only."""


def _extract_json(text: str) -> dict:
    """Tolerate code fences / stray prose around the JSON object."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in grader output: {text[:80]!r}")
    return json.loads(text[start : end + 1])


def grade_by_model(task: str, output: str, with_context: bool = True) -> dict:
    """Ask a second model call to evaluate `output`.

    with_context=False asks for the score alone (no strengths/weaknesses/reasoning).
    The lesson claims this makes scores drift toward ~6; exercise 3 lets you test that.
    """
    prompt = GRADER_PROMPT.format(requirements=CONTENT_REQUIREMENTS, task=task, solution=output)
    if not with_context:
        prompt = prompt.split("Provide your evaluation")[0] + (
            'Respond with a JSON object containing only {"score": <number 1-10>}.'
        )
    response = client.messages.create(
        model=GRADER_MODEL,
        max_tokens=800,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    graded = _extract_json(text)
    graded["score"] = float(graded["score"])
    return graded
