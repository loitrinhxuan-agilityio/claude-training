"""Practice for the lesson "Image support".

    uv run python image_support/practice.py              # run everything
    uv run python image_support/practice.py --trials 5   # more trials per prompt
    uv run python image_support/practice.py --image path/to/photo.jpg --ask "What is in this photo?"
    uv run python image_support/practice.py --url https://example.com/photo.jpg   # URL image block

Parts:
  1. Send one image (base64 image block + text block) and read the reply.
  2. Token cost: compare the lesson's (w*h)/750 estimate with the real usage.
  3. Count marbles with a naive prompt, the lesson's step-by-step prompt, and a
     one-shot example, over several trials, against the known answer (23).
"""

import argparse
import base64
import re
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = "claude-haiku-4-5"  # same model as main.py; supports image input
client = Anthropic()
IMAGES = Path(__file__).parent / "images"
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}


# ------------------------------------------------------------ image blocks
def image_block(path: Path) -> dict:
    """Base64 image block (the lesson's example). Limits: 5MB per image."""
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        sys.exit(f"Unsupported image type {path.suffix!r}; use one of {sorted(MEDIA_TYPES)}")
    data = path.read_bytes()
    if len(data) > 5 * 1024 * 1024:
        sys.exit(f"{path.name} is {len(data) / 1e6:.1f}MB; the limit is 5MB per image")
    return {"type": "image", "source": {
        "type": "base64", "media_type": media_type,
        "data": base64.standard_b64encode(data).decode("utf-8")}}


def url_image_block(url: str) -> dict:
    """The lesson says URLs are supported but shows no example; this is the API shape."""
    return {"type": "image", "source": {"type": "url", "url": url}}


def ask(content: list, max_tokens: int = 600):
    return client.messages.create(
        model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": content}])


def text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def png_size(path: Path):
    """(width, height) from the PNG header, no Pillow needed."""
    data = path.read_bytes()[:24]
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


# ------------------------------------------------------------------ prompts
NAIVE = "How many marbles are in this image?"

# From the lesson (step-by-step methodology), with the same wording.
STEP_BY_STEP = """Analyze this image of marbles and determine the exact count using this methodology:
1. Begin by identifying each unique marble one at a time. Assign each a number as you identify it.
2. Verify your result by counting with a different method. Start from the bottom-left corner and work row by row, from left to right.

What is the exact, verified number of marbles in this image?"""


def last_integer(text: str):
    """Heuristic: the final whole number in the reply is the answer."""
    nums = re.findall(r"\b\d+\b", text)
    return int(nums[-1]) if nums else None


def count_trial(kind: str, target: Path, example: Path, example_count: int):
    if kind == "naive":
        content = [image_block(target), {"type": "text", "text": NAIVE}]
    elif kind == "step-by-step":
        content = [image_block(target), {"type": "text", "text": STEP_BY_STEP}]
    else:  # one-shot: an image with a known count first, then the target
        content = [
            image_block(example),
            {"type": "text", "text": f"This image contains exactly {example_count} marbles."},
            image_block(target),
            {"type": "text", "text": "How many marbles are in this second image? "
                                     "Reply with only the number."},
        ]
    return last_integer(text_of(ask(content)))


# --------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--image", type=Path, help="your own image to describe (part 1)")
    parser.add_argument("--ask", default="Describe this image in two sentences.")
    parser.add_argument("--url", help="send a public image URL instead of base64 (part 1 only)")
    args = parser.parse_args()

    target, example = IMAGES / "marbles_23.png", IMAGES / "marbles_14.png"

    # Part 1: one image + one question
    if args.url:
        block = url_image_block(args.url)
    else:
        block = image_block(args.image or target)
    print("== Part 1: describe an image ==")
    print(text_of(ask([block, {"type": "text", "text": args.ask}])))

    if args.url or args.image:
        return  # parts 2-3 need the generated marble images

    if not target.exists() or not example.exists():
        sys.exit(f"Missing test images: expected {example.name} and {target.name} in {IMAGES}")

    # Part 2: token cost
    w, h = png_size(target)
    response = ask([image_block(target), {"type": "text", "text": "OK?"}], max_tokens=10)
    print(f"\n== Part 2: token cost ==\n{w}x{h}px -> lesson estimate (w*h)/750 = {w * h / 750:.0f} tokens; "
          f"API reported input_tokens = {response.usage.input_tokens} (includes the tiny text prompt)")

    # Part 3: prompting techniques, scored against the known answer
    truth = 23
    print(f"\n== Part 3: count the marbles (true answer: {truth}, {args.trials} trials each) ==")
    for kind in ["naive", "step-by-step", "one-shot"]:
        answers = [count_trial(kind, target, example, 14) for _ in range(args.trials)]
        right = sum(a == truth for a in answers)
        errors = [abs(a - truth) for a in answers if a is not None]
        mae = sum(errors) / len(errors) if errors else float("nan")
        print(f"{kind:<13} answers={answers}  exact={right}/{args.trials}  mean abs error={mae:.1f}")
    print("\nFew trials on one image is a weak test: see the README for how to strengthen it.")


if __name__ == "__main__":
    main()
