"""Safe local document search for directories shared through MCP Roots.

MCP Roots only *tell* the server which directories the client wants to share.
They are not a sandbox: the server must enforce its own boundaries. This module
is that boundary. It has no MCP imports so it can be tested in isolation.

Rules enforced here:
- every path is resolved (symlinks and ``..`` collapsed) before it is checked
- a resolved path must be inside an approved root
- symlinked directories are never traversed
- hidden files and directories are skipped
- only ``.md`` and ``.txt`` files are read
- files larger than ``MAX_FILE_BYTES`` are skipped
- any OS error on a single file skips that file instead of failing the search
"""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

ALLOWED_EXTENSIONS = frozenset({".md", ".txt"})
MAX_FILE_BYTES = 1_000_000
MAX_FILES_SCANNED = 5_000
SNIPPET_CHARS = 240
FILENAME_MATCH_SCORE = 5

# (resolved directory, display name)
Root = tuple[Path, str]


@dataclass(frozen=True)
class DocumentMatch:
    path: Path  # fully resolved, always inside an approved root
    relative_path: str  # relative to its root, for display
    root_name: str
    matched_in: str  # "filename" | "content" | "both"
    score: int
    snippet: str


@dataclass
class SearchStats:
    scanned: int = 0
    skipped: int = 0
    truncated: bool = False


def root_uri_to_path(uri: str) -> Path | None:
    """Convert a ``file://`` root URI to a resolved existing directory.

    Returns None for anything that is not a local, existing directory.
    """
    try:
        parsed = urlparse(str(uri))
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            return None
        # url2pathname already percent-decodes; decoding twice would be a bug.
        path = Path(url2pathname(parsed.path)).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    return path if path.is_dir() else None


def is_within(path: Path, root: Path) -> bool:
    """True if ``path`` is ``root`` or inside it. Both must be resolved."""
    return path == root or path.is_relative_to(root)


def validate_path(candidate: str | os.PathLike[str], roots: list[Path]) -> Path:
    """Resolve ``candidate`` and require it to be inside one of ``roots``.

    Resolving first means ``../`` segments and symlinks are collapsed before the
    check, so neither can be used to escape. Raises PermissionError otherwise.
    """
    try:
        resolved = Path(candidate).resolve()
    except (OSError, RuntimeError, ValueError) as exc:  # e.g. symlink loops
        raise PermissionError(f"Invalid path: {candidate}") from exc
    if not any(is_within(resolved, root) for root in roots):
        raise PermissionError(f"Path is outside the approved roots: {candidate}")
    return resolved


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def _has_hidden_part(resolved: Path, root: Path) -> bool:
    return any(_is_hidden(part) for part in resolved.relative_to(root).parts)


def _containing_root(resolved: Path, roots: list[Path]) -> Path | None:
    for root in roots:
        if is_within(resolved, root):
            return root
    return None


def iter_candidate_files(root: Path, all_roots: list[Path], stats: SearchStats):
    """Yield resolved, safe-to-read files under ``root``."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune hidden directories in place so os.walk never enters them.
        dirnames[:] = sorted(d for d in dirnames if not _is_hidden(d))
        for filename in sorted(filenames):
            if _is_hidden(filename):
                continue
            if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            stats.scanned += 1
            if stats.scanned > MAX_FILES_SCANNED:
                stats.truncated = True
                return

            try:
                resolved = validate_path(Path(dirpath) / filename, all_roots)
                containing = _containing_root(resolved, all_roots)
                if (
                    containing is None
                    # a symlink must not smuggle in a hidden or non-text target
                    or _has_hidden_part(resolved, containing)
                    or resolved.suffix.lower() not in ALLOWED_EXTENSIONS
                ):
                    stats.skipped += 1
                    continue
                info = resolved.stat()
            except (PermissionError, OSError):
                stats.skipped += 1
                continue

            if not resolved.is_file() or info.st_size > MAX_FILE_BYTES:
                stats.skipped += 1
                continue
            yield resolved


def read_text_safely(path: str | os.PathLike[str], roots: list[Path]) -> str | None:
    """Read a text file after re-validating it. None means "skip this file"."""
    try:
        resolved = validate_path(path, roots)
        with open(resolved, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except (PermissionError, OSError):
        return None
    if len(data) > MAX_FILE_BYTES or b"\x00" in data:
        return None  # too large (grew since stat) or binary content
    return data.decode("utf-8", errors="replace")


def _snippet(text: str, index: int) -> str:
    start = max(0, index - SNIPPET_CHARS // 2)
    chunk = text[start : start + SNIPPET_CHARS]
    chunk = " ".join(chunk.split())  # collapse newlines and runs of whitespace
    return ("…" if start > 0 else "") + chunk + ("…" if start + SNIPPET_CHARS < len(text) else "")


def search_root(
    query: str, root: Path, root_name: str, all_roots: list[Path]
) -> tuple[list[DocumentMatch], SearchStats]:
    """Search one approved root. ``all_roots`` is the full approved set."""
    needle = query.strip().lower()
    if not needle:
        raise ValueError("query must not be empty")

    stats = SearchStats()
    matches: list[DocumentMatch] = []
    for path in iter_candidate_files(root, all_roots, stats):
        name_hit = needle in path.name.lower()
        text = read_text_safely(path, all_roots)
        if text is None:
            stats.skipped += 1
            continue

        lowered = text.lower()
        content_hits = lowered.count(needle)
        if not name_hit and content_hits == 0:
            continue

        first = lowered.find(needle)
        snippet = _snippet(text, first) if first >= 0 else _snippet(text, 0)
        matched_in = (
            "both" if name_hit and content_hits else "filename" if name_hit else "content"
        )
        try:
            relative = str(path.relative_to(root))
        except ValueError:  # reached through a symlink to another approved root
            relative = str(path)
        matches.append(
            DocumentMatch(
                path=path,
                relative_path=relative,
                root_name=root_name,
                matched_in=matched_in,
                score=(FILENAME_MATCH_SCORE if name_hit else 0) + content_hits,
                snippet=snippet,
            )
        )
    return matches, stats


def rank_matches(matches: list[DocumentMatch], max_results: int) -> list[DocumentMatch]:
    """Deduplicate by resolved path, order by score, and cap the count."""
    best: dict[Path, DocumentMatch] = {}
    for match in matches:
        current = best.get(match.path)
        if current is None or match.score > current.score:
            best[match.path] = match
    ranked = sorted(best.values(), key=lambda m: (-m.score, str(m.path)))
    return ranked[: max(0, max_results)]


def search_documents(
    query: str, roots: list[Root], max_results: int = 5
) -> list[DocumentMatch]:
    """Search every approved root and return the best ``max_results`` matches."""
    all_roots = [path for path, _ in roots]
    found: list[DocumentMatch] = []
    for path, name in roots:
        matches, _ = search_root(query, path, name, all_roots)
        found.extend(matches)
    return rank_matches(found, max_results)
