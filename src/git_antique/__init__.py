# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""git-antique: Semantic Diff Router & Two-Tier AST Partitioner."""

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
    "ast_canonical_dump",
    "classify_python_file_diff",
    "count_changed_diff_lines",
    "length_prefixed_utf8",
    "nfc_normalize",
    "partition_pull_request",
    "rfc8785_canonical_bytes",
    "rfc8785_sha256",
]
