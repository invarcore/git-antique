# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""CVE-2026-85626 Hardened Git Branch Diff CLI & Markdown Receipt Renderer."""

from __future__ import annotations

import argparse
import json
import subprocess
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import asdict

from git_antique.partitioner import AntiquePartitionReceipt, partition_pull_request


class UnsafeGitRefError(ValueError):
    """Raised when a git ref or path attempts CLI flag injection or traversal."""


def verify_safe_git_ref(ref: str) -> str:
    """CVE-2026-85626 Defense: Reject leading dashes (--upload-pack, --output),
    null bytes, whitespace, or '..' traversal segments in Git revision arguments.
    """
    norm = unicodedata.normalize("NFC", ref).strip()
    if not norm:
        raise UnsafeGitRefError("Git reference cannot be empty")
    if norm.startswith("-"):
        raise UnsafeGitRefError(f"CVE-2026-85626 violation: leading dash forbidden in git ref '{norm}'")
    if chr(0) in norm or ".." in norm.split("/") or any(c.isspace() for c in norm):
        raise UnsafeGitRefError(f"Unsafe characters in git ref '{norm}'")
    return norm


def collect_git_branch_python_pairs(
    repo_dir: str,
    base_ref: str,
    head_ref: str,
    runner: Callable[[Sequence[str], str], bytes] | None = None,
) -> list[tuple[str, str, str]]:
    safe_base = verify_safe_git_ref(base_ref)
    safe_head = verify_safe_git_ref(head_ref)

    def _default_runner(cmd: Sequence[str], cwd: str) -> bytes:
        res = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)
        return res.stdout

    exec_fn = runner or _default_runner
    raw_names = exec_fn(
        ["git", "diff", "--name-only", "-z", safe_base, safe_head, "--"],
        repo_dir,
    )
    null_sep = bytes([0])
    paths = [p.decode("utf-8", errors="replace") for p in raw_names.split(null_sep) if p and p.endswith(b".py")]
    pairs: list[tuple[str, str, str]] = []
    for rel_path in sorted(paths):
        if rel_path.startswith("-") or ".." in rel_path.split("/"):
            raise UnsafeGitRefError(f"Unsafe relative file path '{rel_path}'")
        try:
            before_bytes = exec_fn(["git", "show", f"{safe_base}:{rel_path}"], repo_dir)
            before_src = before_bytes.decode("utf-8")
        except Exception:  # noqa: BLE001
            before_src = ""
        try:
            after_bytes = exec_fn(["git", "show", f"{safe_head}:{rel_path}"], repo_dir)
            after_src = after_bytes.decode("utf-8")
        except Exception:  # noqa: BLE001
            after_src = ""
        pairs.append((rel_path, before_src, after_src))
    return pairs


def render_antique_markdown_summary(receipt: AntiquePartitionReceipt) -> str:
    pipe = chr(124)
    nl = chr(10)
    pct = round(receipt.attention_compression_ratio * 100.0, 1)
    status = "REVIEW REQUIRED" if receipt.requires_human_logic_review else "AUTO-APPROVABLE (ZERO LOGIC DIFF)"
    lines = [
        f"### git-antique Semantic Diff Receipt (`{receipt.receipt_id}`)",
        f"- **Gate Verdict**: **{status}**",
        f"- **Attention Compression**: **{pct}%** ({receipt.total_human_attention_lines} logic lines of {receipt.total_changed_lines} changed lines)",
        "",
        f"{pipe} File {pipe} Classification {pipe} Changed Lines {pipe} Human Attention Lines {pipe}",
        f"{pipe} :--- {pipe} :--- {pipe} ---: {pipe} ---: {pipe}",
    ]
    for f in receipt.files:
        lines.append(
            f"{pipe} `{f.filepath}` {pipe} `{f.classification}` {pipe} {f.changed_lines} {pipe} {f.human_attention_lines} {pipe}"
        )
    return nl.join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="git-antique deterministic semantic diff router")
    parser.add_argument("--repo", default=".", help="Path to Git repository")
    parser.add_argument("--base", default="main", help="Base Git revision")
    parser.add_argument("--head", default="HEAD", help="Head Git revision")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args(argv)

    pairs = collect_git_branch_python_pairs(args.repo, args.base, args.head)
    receipt = partition_pull_request(pairs)
    if args.format == "json":
        print(json.dumps(asdict(receipt), indent=2))
    else:
        print(render_antique_markdown_summary(receipt))
    return 0
