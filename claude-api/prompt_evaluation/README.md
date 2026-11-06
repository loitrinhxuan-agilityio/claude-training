# Practice: Prompt evaluation

Hands-on companion to the lesson
[Prompt evaluation](https://academy.claude.com/courses/building-with-the-claude-api/prompt-evaluation)
(*Building with the Claude API*, lesson 9).

**Task under test:** classify a support message into `category` + `priority` and
return JSON that an application can parse.

| File | Role in the eval |
|---|---|
| `dataset.py` | Test cases with expected answers (14 cases, 8 are edge cases) |
| `prompts.py` | Prompt versions to compare: `v1` (naive), `v2` (engineered), `v3` (fix from eval) |
| `run_eval.py` | Run → grade (code-based) → report → save to `results/*.json` |

Run everything from `claude-api/`:

```bash
uv run python prompt_evaluation/run_eval.py --limit 1   # Option 1: test once
uv run python prompt_evaluation/run_eval.py --limit 3   # Option 2: test a few
uv run python prompt_evaluation/run_eval.py             # Option 3: full eval
```

## What the lesson says → what you see

**Prompt engineering vs. prompt evaluation.** `prompts.py` is engineering (clear
rules, XML tags, multishot examples). `run_eval.py` is evaluation: it measures
whether those techniques actually worked.

**Option 1: test once, ship it.** With `--limit 1`, v2 scores 100%. Looks great.
It also hid that v2 wraps its JSON in code fences, which breaks `json.loads`.

**Option 2: test a few and tweak.** With `--limit 3`, v2 is still 100% correct
and still looks fine. The 3 easy "typical" cases never trigger the one real
weakness of the prompt.

**Option 3: evaluation pipeline.** Results from the full 14-case run
(`claude-haiku-4-5`, temperature 0):

| version | format | category | priority | PASS |
|---|---|---|---|---|
| v1 | 0% | 0% | 0% | 0% |
| v2 | 14% | 100% | 93% | 93% |
| v3 | 100% | 100% | 93% | 93% |

- **v1 → v2** is the prompt-engineering gain. v1 answers sensibly ("Billing/Payment
  Issue, High") but in free-form markdown, which no program can use, so it scores 0%.
- **v2 → v3** is the eval-first loop. The `format` column showed v2 failing 12/14
  on the fence problem even though the classification was right. v3 fixes only that;
  format goes 14% → 100% and nothing else regresses. Without the eval there
  would be no number to prove that.
- **The remaining failure** ("package arrived crushed and cracked") is predicted
  `high`, expected `medium`. That's a prompt or label question, not an obvious bug.
  See exercise 4.

Your numbers may shift by a case or two between runs.

## Exercises

1. **Feel the trap.** Run `--limit 1`, then `--limit 3`, then the full eval. Write
   down which problems each run could and could not have revealed.
2. **Add cases.** Add 5 harder cases to `dataset.py`: a message with two problems,
   an all-caps rant with no real issue, an empty-ish string, a message in another
   language, a very long message. Re-run. Does v3 still hold?
3. **Write a v4.** Change one thing in `prompts.py` (for example remove the
   examples, or change the priority definitions). Re-run and read the table:
   did the change help, hurt, or move the failure somewhere else?
4. **Question the labels.** Decide whether "crushed box, cracked item" really is
   `medium`. If you change the expected label or the priority definitions,
   re-run all versions. Golden answers are part of the eval and can be wrong.
5. **Check the grader.** `grade()` accepts lenient JSON for `category_ok` but
   requires strict JSON for `format_ok`. Change `PASS` to also require
   `format_ok` and see how v2's score changes. The metric you choose decides
   what you optimize.
6. **Variance.** Set `temperature` to 1 in `run_eval.py`, run v3 three times, and
   compare. How much of a score change is noise?

---

# Practice 2: Model-based grading

Companion to the lesson
[Model based grading](https://academy.claude.com/courses/building-with-the-claude-api/model-based-grading).

Classification has one right answer, so code can grade it. A **customer reply** has
no single right string, so this second task drafts one and grades it two ways:

| File | Role |
|---|---|
| `reply_prompts.py` | Task + prompts `r1` (naive) vs `r2` (engineered). The spec is split into `FORMAT_REQUIREMENTS` (code) and `CONTENT_REQUIREMENTS` (model) |
| `grading.py` | `grade_by_code` (length, markdown, language) and `grade_by_model` (strengths, weaknesses, reasoning, score 1-10) |
| `run_reply_eval.py` | Generate → grade both ways → combined score (mean of the two) → report |

```bash
uv run python prompt_evaluation/run_reply_eval.py                # full run
uv run python prompt_evaluation/run_reply_eval.py --no-context   # grader returns only a score
```

How it follows the lesson: criteria first; **Format → code grader, Task following →
model grader**; the grader returns `strengths`, `weaknesses`, `reasoning`, `score`;
`run_test_case` stores score + reasoning; the report averages. One deliberate
deviation: the lesson seeds the grader with a `` ```json `` assistant prefill plus
`stop_sequences`. Newer Claude models reject assistant prefill with a 400, so the
grader uses a plain prompt and tolerant JSON extraction (`_extract_json`).

## Results (generator and grader both `claude-haiku-4-5`, 14 cases, one run)

| version | code | model | combined |
|---|---|---|---|
| r1 | 5.4 | 7.0 | 6.2 |
| r2 | 9.9 | 8.5 | 9.2 |

r1 writes decent content (model 7.0) but breaks the format (markdown headers, far
over 80 words), so code drags it down. Only the combined score shows both.

## Three things the first runs got wrong (all kept as lessons)

1. **Silent grader failure.** `grading.py` built its client before `.env` was loaded,
   so every grader call failed, was swallowed, and the report crashed in `mean()`.
   The report now exits with the first grader error when nothing could be scored.
2. **The generator and grader shared a bad spec.** My requirement said "reply in
   Vietnamese to Vietnamese"; r2 then answered **all 14** messages in Vietnamese, and
   the grader approved ("Vietnamese language"). A model grader inherits the blind
   spots of the spec you give it. A 3-line code check (`language_match`) caught it.
3. **The model grader can't count.** It claimed replies were 86-95 words when they
   were 46-57, and docked points for a violation that did not exist. Fix: move
   anything countable to code and tell the grader not to evaluate it. After the
   split it made 0 word-count claims.

Lesson: **read the grader's reasoning on a sample of cases before trusting its
average.** The `reasoning` field is what made problems 2 and 3 findable.

## The "why ask for reasoning" claim

The lesson says a score-only grader drifts to middling scores (~6). On this small
sample it did **not** drift to 6, but the two graders disagreed:

| grader output | r1 mean / min | r2 mean / min |
|---|---|---|
| strengths + weaknesses + reasoning + score | 7.0 / 6.0 | 8.5 / 7.0 |
| score only (`--no-context`) | 7.4 / 3.0 | 8.9 / 7.0 |

Score-only gave r1 a 3.0 on some cases that the full grader scored at least 6.0, with
nothing to explain it. One run on 14 cases is anecdotal, not a refutation. The
practical benefit shown here is the reasoning you can audit, not a particular
score level.

## Exercises

1. Run the reply eval and open `results/reply-*.json`. For the 3 lowest-scoring
   cases, decide whether you agree with the grader's `reasoning`.
2. Run it 3 times at `temperature=1` for the grader. How far does the average of the
   same replies move? (The lesson calls model graders "somewhat capricious".)
3. Use a stronger model as `GRADER_MODEL` than the generator. Do scores or
   disagreements change? Haiku grading Haiku can share its blind spots.
4. Add a requirement (for example "mention the order number if the customer gave
   one"). Decide whether code or the model should check it, then implement it.
5. Break the grader on purpose: remove the "do not evaluate length" sentence from
   `GRADER_PROMPT` and watch the miscounting come back.

## Where this leads (next lessons)

`Code based grading` (the `grade_by_code` function here, and combining scores)
→ `Quiz on prompt evaluation`.
