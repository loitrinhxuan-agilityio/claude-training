import os
import sys

import pytest

import local_files
from local_files import (
    root_uri_to_path,
    search_documents,
    validate_path,
)

symlinks = pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need privileges on Windows"
)


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "shared"
    path.mkdir()
    return path.resolve()


def search(root, query, max_results=5):
    return search_documents(query, [(root, root.name)], max_results)


# ---------- root_uri_to_path ----------


def test_root_uri_to_path_accepts_directory(root):
    assert root_uri_to_path(root.as_uri()) == root


def test_root_uri_to_path_decodes_percent_encoding_once(tmp_path):
    spaced = (tmp_path / "my notes").resolve()
    spaced.mkdir()
    assert "%20" in spaced.as_uri()
    assert root_uri_to_path(spaced.as_uri()) == spaced


def test_root_uri_to_path_rejects_bad_input(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")
    assert root_uri_to_path("https://example.com/docs") is None
    assert root_uri_to_path("file://remote-host/etc") is None
    assert root_uri_to_path((tmp_path / "missing").as_uri()) is None
    assert root_uri_to_path(a_file.as_uri()) is None


# ---------- searching ----------


def test_finds_content_match_with_snippet(root):
    (root / "notes.md").write_text("Intro\n\nRoots are shared directories.\n")

    results = search(root, "shared directories")

    assert len(results) == 1
    assert results[0].path == root / "notes.md"
    assert results[0].matched_in == "content"
    assert "shared directories" in results[0].snippet


def test_finds_filename_match_and_is_case_insensitive(root):
    (root / "Sampling-Guide.txt").write_text("unrelated body")

    results = search(root, "sampling")

    assert [r.matched_in for r in results] == ["filename"]


def test_filename_and_content_match_ranks_first(root):
    (root / "roots.md").write_text("roots roots")
    (root / "other.md").write_text("roots")

    results = search(root, "roots")

    assert [r.path.name for r in results] == ["roots.md", "other.md"]
    assert results[0].matched_in == "both"


def test_searches_subdirectories(root):
    (root / "deep" / "er").mkdir(parents=True)
    (root / "deep" / "er" / "note.md").write_text("needle")

    assert [r.relative_path for r in search(root, "needle")] == [
        os.path.join("deep", "er", "note.md")
    ]


def test_max_results_limits_output(root):
    for i in range(5):
        (root / f"doc{i}.md").write_text("needle")

    assert len(search(root, "needle", max_results=2)) == 2


def test_overlapping_roots_do_not_duplicate_results(root):
    (root / "sub").mkdir()
    (root / "sub" / "note.md").write_text("needle")

    results = search_documents(
        "needle", [(root, "parent"), (root / "sub", "child")], max_results=10
    )

    assert len(results) == 1


def test_blank_query_is_rejected(root):
    with pytest.raises(ValueError, match="query must not be empty"):
        search(root, "   ")


def test_binary_and_invalid_utf8_files_do_not_crash(root):
    (root / "binary.txt").write_bytes(b"needle\x00\x01\x02")
    (root / "latin.txt").write_bytes(b"needle \xff\xfe caf\xe9")

    results = search(root, "needle")

    assert [r.path.name for r in results] == ["latin.txt"]


@pytest.mark.skipif(sys.platform == "win32", reason="chmod semantics differ")
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores file modes"
)
def test_unreadable_file_is_skipped(root):
    locked = root / "locked.md"
    locked.write_text("needle")
    (root / "ok.md").write_text("needle")
    locked.chmod(0o000)
    try:
        results = search(root, "needle")
    finally:
        locked.chmod(0o600)

    assert [r.path.name for r in results] == ["ok.md"]


# ---------- security ----------


def test_validate_path_rejects_parent_traversal(root, tmp_path):
    (tmp_path / "outside.txt").write_text("secret")

    with pytest.raises(PermissionError):
        validate_path(root / ".." / "outside.txt", [root])


def test_validate_path_accepts_files_inside_root(root):
    (root / "a.md").write_text("x")
    assert validate_path(root / "sub" / ".." / "a.md", [root]) == root / "a.md"


def test_validate_path_rejects_sibling_with_same_prefix(tmp_path):
    root = (tmp_path / "docs").resolve()
    sibling = (tmp_path / "docs-private").resolve()
    root.mkdir()
    sibling.mkdir()
    (sibling / "secret.md").write_text("x")

    with pytest.raises(PermissionError):
        validate_path(sibling / "secret.md", [root])


@symlinks
def test_symlinked_file_escaping_root_is_not_searched(root, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("top-secret needle")
    (root / "link.txt").symlink_to(outside)
    (root / "visible.md").write_text("harmless needle")

    results = search(root, "needle")

    assert [r.path.name for r in results] == ["visible.md"]
    assert all("top-secret" not in r.snippet for r in results)


@symlinks
def test_symlinked_directory_escaping_root_is_not_traversed(root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("needle")
    (root / "linkdir").symlink_to(outside, target_is_directory=True)

    assert search(root, "needle") == []


@symlinks
def test_symlink_to_another_location_inside_root_is_allowed(root):
    (root / "real.md").write_text("needle")
    (root / "alias.md").symlink_to(root / "real.md")

    results = search(root, "needle")

    # both names resolve to one real file, reported once
    assert [r.path for r in results] == [root / "real.md"]


@symlinks
def test_symlink_cannot_reveal_hidden_or_unsupported_targets(root):
    (root / ".private").mkdir()
    (root / ".private" / "notes.md").write_text("needle")
    (root / "innocent.md").symlink_to(root / ".private" / "notes.md")
    (root / "data.pdf").write_text("needle")
    (root / "pretend.txt").symlink_to(root / "data.pdf")

    assert search(root, "needle") == []


def test_hidden_files_and_directories_are_ignored(root):
    (root / ".hidden.md").write_text("needle")
    (root / ".git").mkdir()
    (root / ".git" / "notes.md").write_text("needle")

    assert search(root, "needle") == []


def test_unsupported_extensions_are_ignored(root):
    for name in ("a.pdf", "b.py", "c.md.bak", "d", "e.json"):
        (root / name).write_text("needle")

    assert search(root, "needle") == []


def test_extension_check_is_case_insensitive(root):
    (root / "NOTE.MD").write_text("needle")

    assert [r.path.name for r in search(root, "needle")] == ["NOTE.MD"]


def test_files_over_size_limit_are_skipped(root, monkeypatch):
    monkeypatch.setattr(local_files, "MAX_FILE_BYTES", 100)
    (root / "small.md").write_text("needle")
    (root / "big.md").write_text("needle " + "x" * 200)

    assert [r.path.name for r in search(root, "needle")] == ["small.md"]


def test_read_text_safely_refuses_paths_outside_roots(root, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    assert local_files.read_text_safely(outside, [root]) is None


def test_scan_limit_truncates_instead_of_running_forever(root, monkeypatch):
    monkeypatch.setattr(local_files, "MAX_FILES_SCANNED", 3)
    for i in range(10):
        (root / f"doc{i}.md").write_text("needle")

    matches, stats = local_files.search_root("needle", root, "r", [root])

    assert stats.truncated is True
    assert len(matches) == 3
