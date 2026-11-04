import os

import pytest

from client import make_list_roots_callback, parse_roots
from local_files import root_uri_to_path


def test_root_flag_is_used(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    roots = parse_roots(["--root", str(a), "--root", str(b)], env={})

    assert roots == [a.resolve(), b.resolve()]


def test_root_flag_takes_precedence_over_env(tmp_path):
    flag = tmp_path / "flag"
    env_dir = tmp_path / "env"
    flag.mkdir()
    env_dir.mkdir()

    roots = parse_roots(["--root", str(flag)], env={"MCP_ROOTS": str(env_dir)})

    assert roots == [flag.resolve()]


def test_env_fallback_splits_on_pathsep_and_ignores_blanks(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    roots = parse_roots([], env={"MCP_ROOTS": f"{a}{os.pathsep}{os.pathsep}{b}"})

    assert roots == [a.resolve(), b.resolve()]


def test_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "notes").mkdir()

    assert parse_roots(["--root", "~/notes"], env={}) == [(tmp_path / "notes").resolve()]


def test_duplicate_roots_are_removed(tmp_path):
    assert parse_roots(["--root", str(tmp_path), "--root", str(tmp_path)], env={}) == [
        tmp_path.resolve()
    ]


def test_no_roots_selected_returns_empty_list():
    assert parse_roots([], env={}) == []


def test_missing_directory_exits(tmp_path):
    with pytest.raises(SystemExit, match="does not exist"):
        parse_roots(["--root", str(tmp_path / "missing")], env={})


def test_file_instead_of_directory_exits(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")

    with pytest.raises(SystemExit, match="not a directory"):
        parse_roots(["--root", str(a_file)], env={})


@pytest.mark.asyncio
async def test_callback_returns_selected_directories_as_file_uris(tmp_path):
    spaced = (tmp_path / "my notes").resolve()
    spaced.mkdir()
    other = (tmp_path / "other").resolve()
    other.mkdir()

    callback = make_list_roots_callback([spaced, other])
    result = await callback(None)

    assert [root.name for root in result.roots] == ["my notes", "other"]
    uris = [str(root.uri) for root in result.roots]
    assert all(uri.startswith("file://") for uri in uris)
    # the URIs must round-trip back to exactly the directories that were selected
    assert [root_uri_to_path(uri) for uri in uris] == [spaced, other]


@pytest.mark.asyncio
async def test_callback_with_no_paths_returns_empty_roots():
    result = await make_list_roots_callback([])(None)

    assert result.roots == []
