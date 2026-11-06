"""Model-based grading eval: compare reply prompts r1 vs r2.

Usage (from the claude-api/ folder):
    uv run python prompt_evaluation/run_reply_eval.py
    uv run python prompt_evaluation/run_reply_eval.py --no-context   # score-only grader (exercise 3)
    uv run python prompt_evaluation/run_reply_eval.py --limit 4
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import mean

from anthropic import Anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from dataset import CASES  # noqa: E402
from grading import grade_by_code, grade_by_model  # noqa: E402
from reply_prompts import REPLY_PROMPTS  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = "claude-haiku-4-5"
client = Anthropic()


def run_prompt(version: str, message: str) -> str:
    response = client.messages.create(
        model=MODEL, max_tokens=500, temperature=0, **REPLY_PROMPTS[version](message)
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def run_test_case(version: str, case: tuple, with_context: bool) -> dict:
    message, _cat, _pri, why = case
    output = run_prompt(version, message)

    code = grade_by_code(output, message)
    try:
        model = grade_by_model(message, output, with_context)
    except Exception as e:  # a flaky grader must not crash the whole eval
        model = {"score": None, "reasoning": f"GRADER ERROR: {e}"}

    combined = mean([code["score"], model["score"]]) if model["score"] is not None else None
    return {
        "version": version, "message": message, "why": why, "output": output,
        "code_score": code["score"], "code_checks": code["checks"],
        "model_score": model["score"], "reasoning": model.get("reasoning"),
        "strengths": model.get("strengths"), "weaknesses": model.get("weaknesses"),
        "score": combined,
    }


def report(results: dict[str, list[dict]]):
    print(f"\nGenerator: {MODEL}   Grader: {MODEL}\n")
    print(f"{'version':<8}{'code':>8}{'model':>8}{'combined':>10}{'min model':>11}")
    for v, rows in results.items():
        ok = [r for r in rows if r["score"] is not None]
        if not ok:
            errors = {r["reasoning"] for r in rows}
            sys.exit(f"{v}: every grader call failed, nothing to score. First error: {next(iter(errors))}")
        print(f"{v:<8}{mean(r['code_score'] for r in ok):>8.1f}{mean(r['model_score'] for r in ok):>8.1f}"
              f"{mean(r['score'] for r in ok):>10.1f}{min(r['model_score'] for r in ok):>11.1f}"
              + (f"   ({len(rows) - len(ok)} grader errors)" if len(ok) != len(rows) else ""))

    for v, rows in results.items():
        worst = sorted((r for r in rows if r["score"] is not None), key=lambda r: r["score"])[:3]
        print(f"\n--- {v}: 3 lowest-scoring cases ---")
        for r in worst:
            print(f"  [{r['why']}] {r['message'][:55]!r}  code={r['code_score']} model={r['model_score']}")
            print(f"     reply: {r['output'][:110].strip()!r}")
            print(f"     grader: {(r['reasoning'] or '')[:200]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", default=list(REPLY_PROMPTS), choices=list(REPLY_PROMPTS))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-context", action="store_true",
                        help="grader returns only a score (no strengths/weaknesses/reasoning)")
    args = parser.parse_args()

    cases = CASES[: args.limit] if args.limit else CASES
    results = {}
    for v in args.versions:
        with ThreadPoolExecutor(max_workers=5) as pool:
            results[v] = list(pool.map(lambda c: run_test_case(v, c, not args.no_context), cases))
    report(results)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    tag = "reply-noctx" if args.no_context else "reply"
    out = out_dir / f"{tag}-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nFull results saved to {out}")


if __name__ == "__main__":
    main()
