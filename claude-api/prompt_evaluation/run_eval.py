"""Steps 3-5: run every prompt version over the dataset, grade, compare.

Usage (from the claude-api/ folder):
    uv run python prompt_evaluation/run_eval.py                  # full eval, all versions
    uv run python prompt_evaluation/run_eval.py --limit 1        # "Option 1": test once
    uv run python prompt_evaluation/run_eval.py --limit 3        # "Option 2": test a few
    uv run python prompt_evaluation/run_eval.py --versions v2    # one version only
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from dataset import CASES, CATEGORIES, PRIORITIES  # noqa: E402
from prompts import PROMPTS  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = "claude-haiku-4-5"  # same model as main.py; cheap enough to run evals often
client = Anthropic()


# ---------------------------------------------------------------- run (step 3)
def run_prompt(version: str, message: str) -> str:
    kwargs = PROMPTS[version](message)
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        temperature=0,  # reduce noise so score changes come from the prompt
        **kwargs,
    )
    return "".join(b.text for b in response.content if b.type == "text")


# --------------------------------------------------------------- grade (step 4)
def grade(output: str, exp_category: str, exp_priority: str) -> dict:
    """Code-based grading: parse the output and compare to the golden answer."""
    strict_ok = True
    try:
        parsed = json.loads(output.strip())
    except json.JSONDecodeError:
        strict_ok = False
        match = re.search(r"\{.*?\}", output, re.S)  # lenient fallback
        try:
            parsed = json.loads(match.group(0)) if match else {}
        except json.JSONDecodeError:
            parsed = {}

    category = str(parsed.get("category", "")).lower()
    priority = str(parsed.get("priority", "")).lower()
    return {
        "format_ok": strict_ok and category in CATEGORIES and priority in PRIORITIES,
        "category_ok": category == exp_category,
        "priority_ok": priority == exp_priority,
        "got_category": category or None,
        "got_priority": priority or None,
    }


def evaluate(version: str, cases: list) -> list[dict]:
    def one(case):
        message, exp_cat, exp_pri, why = case
        output = run_prompt(version, message)
        g = grade(output, exp_cat, exp_pri)
        g["passed"] = g["category_ok"] and g["priority_ok"]
        return {"version": version, "message": message, "why": why,
                "expected": [exp_cat, exp_pri], "output": output, **g}

    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(one, cases))


# -------------------------------------------------------------- report (step 5)
def rate(rows, key):
    return 100 * sum(r[key] for r in rows) / len(rows)


def report(results: dict[str, list[dict]]):
    n = len(next(iter(results.values())))
    print(f"\nModel: {MODEL}   Cases: {n}\n")
    print(f"{'version':<8}{'format':>9}{'category':>10}{'priority':>10}{'PASS':>8}")
    for version, rows in results.items():
        print(f"{version:<8}{rate(rows, 'format_ok'):>8.0f}%{rate(rows, 'category_ok'):>9.0f}%"
              f"{rate(rows, 'priority_ok'):>9.0f}%{rate(rows, 'passed'):>7.0f}%")

    for version, rows in results.items():
        failed = [r for r in rows if not r["passed"]]
        print(f"\n--- {version}: {len(failed)} failing case(s) ---")
        for r in failed:
            print(f"  [{r['why']}] {r['message'][:60]!r}")
            print(f"     expected={tuple(r['expected'])}  got=({r['got_category']}, {r['got_priority']})")
            print(f"     raw output: {r['output'][:90].strip()!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", default=list(PROMPTS), choices=list(PROMPTS))
    parser.add_argument("--limit", type=int, default=None, help="only the first N cases")
    args = parser.parse_args()

    cases = CASES[: args.limit] if args.limit else CASES
    results = {v: evaluate(v, cases) for v in args.versions}
    report(results)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nFull results saved to {out}")


if __name__ == "__main__":
    main()
