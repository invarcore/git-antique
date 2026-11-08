# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""Deterministic Two-Tier AST Diff Partitioner and RFC 8785 Receipt Router (v2)."""

from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import json
import operator
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


def nfc_normalize(value: str) -> str:
    """Normalize string to Unicode NFC before canonicalization or hashing."""
    return unicodedata.normalize("NFC", value)


def length_prefixed_utf8(value: str) -> str:
    """Format string with its exact UTF-8 byte length: '{byte_len}:{nfc_str}'."""
    norm = nfc_normalize(value)
    byte_len = len(norm.encode("utf-8"))
    return f"{byte_len}:{norm}"


def rfc8785_canonical_bytes(payload: Any) -> bytes:
    """Serialize payload into deterministic RFC 8785 canonical UTF-8 JSON bytes."""

    def _normalize_obj(obj: Any) -> Any:
        if isinstance(obj, str):
            return nfc_normalize(obj)
        if isinstance(obj, Mapping):
            return {nfc_normalize(str(k)): _normalize_obj(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_normalize_obj(x) for x in obj]
        return obj

    normalized = _normalize_obj(payload)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def rfc8785_sha256(payload: Any) -> str:
    """Compute SHA-256 hex digest over RFC 8785 canonical JSON bytes."""
    return hashlib.sha256(rfc8785_canonical_bytes(payload)).hexdigest()


class _CosmeticStripper(ast.NodeTransformer):
    """Tier 0 Normalizer (v2 Hardened):

    - Strips module/class/function docstrings.
    - Sorts ONLY contiguous leading top-level Import statements at the start of a module
      (P0-2 fix: never hoists late imports across executable statements with side effects).
    """

    def _strip_docstring(self, body: list[ast.stmt]) -> list[ast.stmt]:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            return body[1:] or [ast.Pass()]
        return body

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        body = self._strip_docstring(node.body)
        leading_imports: list[ast.Import] = []
        idx = 0
        while operator.lt(idx, len(body)) and isinstance(body[idx], ast.Import):
            leading_imports.append(body[idx])
            idx += 1
        if leading_imports:
            all_aliases = sorted(
                (a for imp in leading_imports for a in imp.names),
                key=lambda a: (a.name, a.asname or ""),
            )
            node.body = [ast.Import(names=all_aliases)] + body[idx:]
        else:
            node.body = body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node


class _IsomorphicNormalizer(_CosmeticStripper):
    """Tier 1 Normalizer (v2 Hardened):

    - P0-1 Fix: Preserves public keyword-callable parameter names (args.args and args.kwonlyargs);
      only alpha-normalizes posonlyargs and strictly internal function-local variables.
    - P0-3 Fix: Preserves AnnAssign inside ClassDef and Module scopes; strips AnnAssign ONLY
      inside function scopes.
    - P1-1 Fix: Respects 'global' and 'nonlocal' declarations and pins read-before-write names.
    """

    def __init__(self) -> None:
        super().__init__()
        self._scope_stack: list[dict[str, str]] = []
        self._pinned_names_stack: list[set[str]] = []

    def _in_function_scope(self) -> bool:
        return operator.gt(len(self._scope_stack), 0)

    def _canonical_local(self, name: str, allow_bind: bool) -> str:
        if not self._scope_stack:
            return name
        scope = self._scope_stack[-1]
        pinned = self._pinned_names_stack[-1]
        if name in pinned:
            return name
        if name in scope:
            return scope[name]
        if allow_bind:
            canon = f"__local_{len(scope)}"
            scope[name] = canon
            return canon
        pinned.add(name)
        return name

    def _collect_pinned_declarations(self, body: list[ast.stmt]) -> set[str]:
        pinned: set[str] = set()
        for stmt in body:
            for sub in ast.walk(stmt):
                if isinstance(sub, (ast.Global, ast.Nonlocal)):
                    pinned.update(sub.names)
        return pinned

    def _visit_callable(self, node: Any) -> Any:
        node.returns = None
        scope: dict[str, str] = {}
        pinned = self._collect_pinned_declarations(node.body)
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
            pinned.add(arg.arg)
        if node.args.vararg:
            node.args.vararg.annotation = None
        if node.args.kwarg:
            node.args.kwarg.annotation = None

        self._scope_stack.append(scope)
        self._pinned_names_stack.append(pinned)
        try:
            for pos_arg in node.args.posonlyargs:
                pos_arg.annotation = None
                pos_arg.arg = self._canonical_local(pos_arg.arg, allow_bind=True)
            node.body = self._strip_docstring(node.body)
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                visited = self.visit(stmt)
                if isinstance(visited, ast.stmt):
                    new_body.append(visited)
            node.body = new_body or [ast.Pass()]
        finally:
            self._scope_stack.pop()
            self._pinned_names_stack.pop()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visit_callable(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visit_callable(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        if not self._in_function_scope():
            return self.generic_visit(node)
        if node.value is None:
            return ast.Pass()
        target = self.visit(node.target)
        val = self.visit(node.value)
        return ast.Assign(targets=[target], value=val)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        is_store = isinstance(node.ctx, ast.Store)
        node.id = self._canonical_local(node.id, allow_bind=is_store)
        return node


def ast_canonical_dump(source: str, tier: int) -> str:
    """Return canonical AST string for Tier 0 (cosmetic) or Tier 1 (isomorphic)."""
    tree = ast.parse(nfc_normalize(source))
    if tier == 0:
        transformed = _CosmeticStripper().visit(copy.deepcopy(tree))
    else:
        transformed = _IsomorphicNormalizer().visit(copy.deepcopy(tree))
    ast.fix_missing_locations(transformed)
    return ast.dump(transformed, annotate_fields=True, include_attributes=False)


@dataclass(frozen=True)
class FilePartitionVerdict:
    filepath: str
    classification: str
    changed_lines: int
    human_attention_lines: int
    before_sha256: str
    after_sha256: str
    tier0_ast_digest: str
    tier1_ast_digest: str


@dataclass(frozen=True)
class AntiquePartitionReceipt:
    files: tuple[FilePartitionVerdict, ...]
    total_changed_lines: int
    total_human_attention_lines: int
    attention_compression_ratio: float
    requires_human_logic_review: bool
    receipt_id: str


def count_changed_diff_lines(before_src: str, after_src: str) -> int:
    diff = list(
        difflib.unified_diff(
            before_src.splitlines(),
            after_src.splitlines(),
            lineterm="",
        )
    )
    return sum(
        1
        for line in diff
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    )


def classify_python_file_diff(filepath: str, before_src: str, after_src: str) -> FilePartitionVerdict:
    norm_before = nfc_normalize(before_src)
    norm_after = nfc_normalize(after_src)
    before_sha = hashlib.sha256(norm_before.encode("utf-8")).hexdigest()
    after_sha = hashlib.sha256(norm_after.encode("utf-8")).hexdigest()
    changed_lines = count_changed_diff_lines(norm_before, norm_after)

    try:
        t0_before = ast_canonical_dump(norm_before, tier=0)
        t0_after = ast_canonical_dump(norm_after, tier=0)
        t1_before = ast_canonical_dump(norm_before, tier=1)
        t1_after = ast_canonical_dump(norm_after, tier=1)
    except SyntaxError:
        return FilePartitionVerdict(
            filepath=filepath,
            classification="SEMANTIC_LOGIC_MUTATION",
            changed_lines=changed_lines,
            human_attention_lines=changed_lines,
            before_sha256=before_sha,
            after_sha256=after_sha,
            tier0_ast_digest="SYNTAX_ERROR",
            tier1_ast_digest="SYNTAX_ERROR",
        )

    t0_digest = hashlib.sha256(t0_after.encode("utf-8")).hexdigest()[:16]
    t1_digest = hashlib.sha256(t1_after.encode("utf-8")).hexdigest()[:16]

    if t0_before == t0_after:
        return FilePartitionVerdict(
            filepath=filepath,
            classification="TRIVIAL_COSMETIC",
            changed_lines=changed_lines,
            human_attention_lines=0,
            before_sha256=before_sha,
            after_sha256=after_sha,
            tier0_ast_digest=t0_digest,
            tier1_ast_digest=t1_digest,
        )

    if t1_before == t1_after:
        return FilePartitionVerdict(
            filepath=filepath,
            classification="STRUCTURAL_ISOMORPHIC",
            changed_lines=changed_lines,
            human_attention_lines=0,
            before_sha256=before_sha,
            after_sha256=after_sha,
            tier0_ast_digest=t0_digest,
            tier1_ast_digest=t1_digest,
        )

    return FilePartitionVerdict(
        filepath=filepath,
        classification="SEMANTIC_LOGIC_MUTATION",
        changed_lines=changed_lines,
        human_attention_lines=changed_lines,
        before_sha256=before_sha,
        after_sha256=after_sha,
        tier0_ast_digest=t0_digest,
        tier1_ast_digest=t1_digest,
    )


def partition_pull_request(file_pairs: Sequence[tuple[str, str, str]]) -> AntiquePartitionReceipt:
    verdicts = tuple(classify_python_file_diff(path, before, after) for path, before, after in file_pairs)
    total_changed = sum(v.changed_lines for v in verdicts)
    total_attention = sum(v.human_attention_lines for v in verdicts)
    compression = round(1.0 - (total_attention / total_changed), 4) if operator.gt(total_changed, 0) else 1.0
    requires_review = any(v.classification == "SEMANTIC_LOGIC_MUTATION" for v in verdicts)
    canonical_payload = {
        "files": [
            {
                "after_sha256": v.after_sha256,
                "before_sha256": v.before_sha256,
                "changed_lines": v.changed_lines,
                "classification": v.classification,
                "filepath": length_prefixed_utf8(v.filepath),
                "human_attention_lines": v.human_attention_lines,
            }
            for v in verdicts
        ],
        "v": "antique-rfc8785-v2",
    }
    digest = rfc8785_sha256(canonical_payload)
    return AntiquePartitionReceipt(
        files=verdicts,
        total_changed_lines=total_changed,
        total_human_attention_lines=total_attention,
        attention_compression_ratio=compression,
        requires_human_logic_review=requires_review,
        receipt_id=f"@antique_receipt:sha256:{digest[:24]}",
    )
