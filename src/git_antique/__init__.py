# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""git-antique: Semantic Diff Router & Two-Tier AST Partitioner."""

from git_antique.cli import (
    UnsafeGitRefError,
    collect_git_branch_python_pairs,
    render_antique_markdown_summary,
    verify_safe_git_ref,
)
from git_antique.partitioner import (
    AntiquePartitionReceipt,
    FilePartitionVerdict,
    ast_canonical_dump,
    classify_python_file_diff,
    count_changed_diff_lines,
    length_prefixed_utf8,
    nfc_normalize,
    partition_pull_request,
    rfc8785_canonical_bytes,
    rfc8785_sha256,
)

__all__ = [
    "AntiquePartitionReceipt",
    "FilePartitionVerdict",
    "UnsafeGitRefError",
    "ast_canonical_dump",
    "classify_python_file_diff",
    "collect_git_branch_python_pairs",
    "count_changed_diff_lines",
    "length_prefixed_utf8",
    "nfc_normalize",
    "partition_pull_request",
    "render_antique_markdown_summary",
    "rfc8785_canonical_bytes",
    "rfc8785_sha256",
    "verify_safe_git_ref",
]
