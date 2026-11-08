# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

import pytest

from git_antique.cli import (
    UnsafeGitRefError,
    collect_git_branch_python_pairs,
    main,
    render_antique_markdown_summary,
    verify_safe_git_ref,
)
from git_antique.partitioner import partition_pull_request


def test_verify_safe_git_ref_firewall() -> None:
    # Reject leading dashes (CVE-2026-85626)
    with pytest.raises(UnsafeGitRefError, match="CVE-2026-85626 violation"):
        verify_safe_git_ref("--upload-pack=/tmp/evil")

    with pytest.raises(UnsafeGitRefError, match="CVE-2026-85626 violation"):
        verify_safe_git_ref("-o")

    # Reject empty or whitespace
    with pytest.raises(UnsafeGitRefError, match="cannot be empty"):
        verify_safe_git_ref("   ")

    # Reject traversal segments
    with pytest.raises(UnsafeGitRefError, match="Unsafe characters"):
        verify_safe_git_ref("refs/heads/../../etc/passwd")

    # Reject null bytes and spaces
    with pytest.raises(UnsafeGitRefError, match="Unsafe characters"):
        verify_safe_git_ref("main\x00evil")

    with pytest.raises(UnsafeGitRefError, match="Unsafe characters"):
        verify_safe_git_ref("main branch")

    # Valid refs pass through
    assert verify_safe_git_ref("main") == "main"
    assert verify_safe_git_ref("refs/heads/feature/x") == "refs/heads/feature/x"
    assert verify_safe_git_ref("v1.2.3") == "v1.2.3"


def test_collect_git_branch_python_pairs() -> None:
    def fake_git(cmd, cwd: str) -> bytes:
        if "diff" in cmd:
            return (
                b"src/clean.py"
                + bytes([0])
                + b"README.md"
                + bytes([0])
                + b"src/new.py"
                + bytes([0])
                + b"src/deleted.py"
                + bytes([0])
            )
        if "main:src/clean.py" in cmd:
            return b"def f(x):\n    return x\n"
        if "HEAD:src/clean.py" in cmd:
            return b"def f(x: int) -> int:\n    '''doc'''\n    return x\n"
        if "main:src/new.py" in cmd:
            raise RuntimeError("File does not exist in main")
        if "HEAD:src/new.py" in cmd:
            return b"def g(): return 1\n"
        if "main:src/deleted.py" in cmd:
            return b"def deleted(): return 0\n"
        if "HEAD:src/deleted.py" in cmd:
            raise RuntimeError("File does not exist in HEAD")
        return b""

    pairs = collect_git_branch_python_pairs("/tmp/repo", "main", "HEAD", runner=fake_git)
    assert len(pairs) == 3
    assert pairs[0][0] == "src/clean.py"
    assert pairs[0][1] == "def f(x):\n    return x\n"
    assert "'''doc'''" in pairs[0][2]
    # Deleted file fallback after_src is empty
    assert pairs[1][0] == "src/deleted.py"
    assert pairs[1][1] == "def deleted(): return 0\n"
    assert pairs[1][2] == ""
    # New file fallback before_src is empty
    assert pairs[2][0] == "src/new.py"
    assert pairs[2][1] == ""
    assert pairs[2][2] == "def g(): return 1\n"


def test_collect_git_branch_rejects_unsafe_paths() -> None:
    def fake_git_traversal(cmd, cwd: str) -> bytes:
        return b"../escape.py" + bytes([0])

    with pytest.raises(UnsafeGitRefError, match="Unsafe relative file path"):
        collect_git_branch_python_pairs("/tmp/repo", "main", "HEAD", runner=fake_git_traversal)


def test_render_antique_markdown_summary() -> None:
    files = [
        (
            "src/clean.py",
            "def f(x):\n    return x\n",
            "def f(x: int) -> int:\n    '''doc'''\n    return x\n",
        ),
        (
            "src/policy.py",
            "def allow(): return False\n",
            "def allow(): return True\n",
        ),
    ]
    receipt = partition_pull_request(files)
    md = render_antique_markdown_summary(receipt)
    assert "### git-antique Semantic Diff Receipt" in md
    assert "REVIEW REQUIRED" in md
    assert "| `src/clean.py` | `STRUCTURAL_ISOMORPHIC` |" in md
    assert "| `src/policy.py` | `SEMANTIC_LOGIC_MUTATION` |" in md


def test_main_cli_markdown_and_json(capsys, monkeypatch) -> None:
    # Use real git repo of git-antique
    exit_code = main(["--base", "HEAD~1", "--head", "HEAD", "--format", "markdown"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "git-antique Semantic Diff Receipt" in captured.out

    exit_code_json = main(["--base", "HEAD~1", "--head", "HEAD", "--format", "json"])
    assert exit_code_json == 0
    captured_json = capsys.readouterr()
    assert '"receipt_id":' in captured_json.out
