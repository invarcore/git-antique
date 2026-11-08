# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""Unit & Adversarial Test Suite for git-antique AST Partitioner."""

from __future__ import annotations

import operator
import time

from git_antique.partitioner import (
    classify_python_file_diff,
    length_prefixed_utf8,
    partition_pull_request,
    rfc8785_canonical_bytes,
    rfc8785_sha256,
)


def test_tier0_cosmetic_docstring_and_imports() -> None:
    before = "import sys\nimport os\ndef compute(x):\n    '''Old doc'''\n    return x + 1\ndef doc_only():\n    '''Only a docstring'''\n"
    after = "import os, sys\n# comment\ndef compute(x):\n    '''Updated doc 🚀'''\n    return x + 1\ndef doc_only():\n    pass\n"
    verdict = classify_python_file_diff("src/math_utils.py", before, after)
    assert verdict.classification == "TRIVIAL_COSMETIC"
    assert verdict.human_attention_lines == 0
    assert operator.gt(verdict.changed_lines, 0)


def test_tier1_structural_isomorphic_types_and_local_rename() -> None:
    before = "def process_items(items):\n    total = 0\n    for val in items:\n        total += val\n    return total\n"
    after = "def process_items(item_list: list) -> int:\n    running_sum: int = 0\n    for element in item_list:\n        running_sum += element\n    return running_sum\n"
    verdict = classify_python_file_diff("src/processor.py", before, after)
    assert verdict.classification == "STRUCTURAL_ISOMORPHIC"
    assert verdict.human_attention_lines == 0


def test_tier2_semantic_logic_mutation_detected() -> None:
    before = "def check_limit(amount: int) -> bool:\n    return amount == 1000\n"
    after = "def check_limit(amount: int) -> bool:\n    return amount != 1000\n"
    verdict = classify_python_file_diff("src/policy.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"
    assert verdict.human_attention_lines == verdict.changed_lines


def test_external_call_mutation_is_never_alpha_normalized() -> None:
    before = "def authorize(user):\n    return verify_token_strict(user)\n"
    after = "def authorize(user):\n    return verify_token_lenient(user)\n"
    verdict = classify_python_file_diff("src/auth_gate.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"
    assert verdict.human_attention_lines == verdict.changed_lines


def test_syntax_error_fails_closed_to_semantic_mutation() -> None:
    before = "def ok(x):\n    return x + 1\n"
    after = "def ok(x):\n    return x +\n"
    verdict = classify_python_file_diff("src/broken.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"
    assert verdict.tier0_ast_digest == "SYNTAX_ERROR"
    assert verdict.human_attention_lines == verdict.changed_lines


def test_pr_partition_compression_ratio_and_nfc_receipt() -> None:
    nfc_path = "src/café_router.py"
    nfd_path = "src/café_router.py"
    assert length_prefixed_utf8(nfc_path) == length_prefixed_utf8(nfd_path)
    assert length_prefixed_utf8(nfc_path).startswith("19:")
    assert rfc8785_sha256({"path": nfc_path}) == rfc8785_sha256({"path": nfd_path})

    files = [
        (
            "src/a.py",
            "import b, a\ndef f(x):\n    return x\n",
            "import a, b\ndef f(x: int) -> int:\n    '''doc'''\n    return x\n",
        ),
        (
            "src/b.py",
            "def g(y):\n    return y + 1\n",
            "def g(z: int) -> int:\n    return z + 1\n",
        ),
        (
            "src/auth.py",
            "def allow(u):\n    return u.is_admin\n",
            "def allow(u):\n    return True\n",
        ),
    ]
    t0 = time.perf_counter()
    receipt = partition_pull_request(files)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert operator.lt(elapsed_ms, 25.0)
    assert receipt.requires_human_logic_review is True
    assert operator.gt(receipt.attention_compression_ratio, 0.60)
    assert receipt.receipt_id.startswith("@antique_receipt:sha256:")


def test_classes_async_functions_and_annassign() -> None:
    # Test ClassDef and AsyncFunctionDef docstring stripping and type stripping
    src_before = """
class Worker:
    '''Class doc'''
    def run(self, *args, **kwargs):
        '''Doc'''
        x: int = 1
        y: int
        return x

    async def arun(self, val):
        '''Async doc'''
        return val
"""
    src_after = """
class Worker:
    '''Updated class doc'''
    def run(self, *args: str, **kwargs: int) -> int:
        '''Updated doc'''
        x: int = 1
        y: str
        return x

    async def arun(self, val: int) -> int:
        '''Updated async doc'''
        return val
"""
    verdict = classify_python_file_diff("src/worker.py", src_before, src_after)
    assert verdict.classification in ("TRIVIAL_COSMETIC", "STRUCTURAL_ISOMORPHIC")
    assert verdict.human_attention_lines == 0

    # Empty PR returns compression ratio 1.0 and requires_review False
    empty_receipt = partition_pull_request([])
    assert empty_receipt.total_changed_lines == 0
    assert empty_receipt.attention_compression_ratio == 1.0
    assert empty_receipt.requires_human_logic_review is False

    # Check canonical serialization on lists
    canon = rfc8785_canonical_bytes([1, "café", {"k": "v"}])
    assert b"caf\xc3\xa9" in canon
