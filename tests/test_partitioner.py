# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

import operator
import time

from git_antique.partitioner import (
    ast_canonical_dump,
    classify_python_file_diff,
    length_prefixed_utf8,
    partition_pull_request,
    rfc8785_canonical_bytes,
    rfc8785_sha256,
)


def test_tier0_trivial_cosmetic_diff_detected() -> None:
    before = "'''Docstring.'''\nimport sys\nimport os\n\ndef run():\n    '''Inner doc.'''\n    return 1\n"
    after = "import os\nimport sys\n\ndef run():\n    return 1\n"
    verdict = classify_python_file_diff("src/app.py", before, after)
    assert verdict.classification == "TRIVIAL_COSMETIC"
    assert verdict.human_attention_lines == 0


def test_p0_2_late_import_hoisting_across_side_effect_is_semantic_mutation() -> None:
    before = "import os\nos.environ['CUDA_VISIBLE_DEVICES'] = '0'\nimport torch\n"
    after = "import os\nimport torch\nos.environ['CUDA_VISIBLE_DEVICES'] = '0'\n"
    verdict = classify_python_file_diff("src/gpu_init.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"


def test_p0_1_public_keyword_param_rename_triggers_semantic_mutation() -> None:
    before = "def transfer(sender: str, recipient: str) -> str:\n    return sender + recipient\n"
    after = "def transfer(from_acct: str, to_acct: str) -> str:\n    return from_acct + to_acct\n"
    verdict = classify_python_file_diff("src/payments.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"


def test_p0_1_posonly_and_local_var_rename_is_structural_isomorphic() -> None:
    before = (
        "def process_items(items, /):\n    total = 0\n    for val in items:\n        total += val\n    return total\n"
    )
    after = "def process_items(item_list: list, /) -> int:\n    running_sum: int = 0\n    for element in item_list:\n        running_sum += element\n    return running_sum\n"
    verdict = classify_python_file_diff("src/processor.py", before, after)
    assert verdict.classification == "STRUCTURAL_ISOMORPHIC"
    assert verdict.human_attention_lines == 0


def test_p0_3_pydantic_or_dataclass_field_deletion_is_semantic_mutation() -> None:
    before = "class UserSchema:\n    user_id: str\n    is_admin: bool\n"
    after = "class UserSchema:\n    user_id: str\n"
    verdict = classify_python_file_diff("src/schemas.py", before, after)
    assert verdict.classification == "SEMANTIC_LOGIC_MUTATION"


def test_p1_1_global_and_nonlocal_declarations_preserve_names() -> None:
    src = "x = 1\ndef update():\n    global x\n    x = x + 1\n    return x\n"
    t1 = ast_canonical_dump(src, tier=1)
    assert "x" in t1


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


def test_async_function_isomorphic_and_cosmetic() -> None:
    before = "async def fetch(url, /):\n    '''Doc.'''\n    resp = await get(url)\n    return resp\n"
    after = "async def fetch(endpoint: str, /):\n    data = await get(endpoint)\n    return data\n"
    verdict = classify_python_file_diff("src/client.py", before, after)
    assert verdict.classification == "STRUCTURAL_ISOMORPHIC"


def test_class_def_docstring_stripping() -> None:
    before = "class Service:\n    '''Service doc.'''\n    def run(self):\n        return 1\n"
    after = "class Service:\n    def run(self):\n        return 1\n"
    verdict = classify_python_file_diff("src/svc.py", before, after)
    assert verdict.classification == "TRIVIAL_COSMETIC"


def test_empty_files_partition() -> None:
    receipt = partition_pull_request([])
    assert receipt.attention_compression_ratio == 1.0
    assert receipt.total_changed_lines == 0
    assert receipt.requires_human_logic_review is False


def test_rfc8785_canonical_serialization_nested() -> None:
    payload = {"b": [1, 2, {"c": "test"}], "a": "norm"}
    b = rfc8785_canonical_bytes(payload)
    assert b == b'{"a":"norm","b":[1,2,{"c":"test"}]}'


def test_repeated_local_var_reuse() -> None:
    src = "def calc(x, /):\n    y = x + 1\n    z = y + y\n    return z\n"
    dump = ast_canonical_dump(src, tier=1)
    assert "__local_0" in dump


def test_pr_partition_compression_ratio_and_nfc_receipt() -> None:
    nfc_path = "src/caf\u00e9_service.py"
    nfd_path = "src/cafe\u0301_service.py"
    assert length_prefixed_utf8(nfc_path) == length_prefixed_utf8(nfd_path)
    assert length_prefixed_utf8(nfc_path).startswith(f"{len(nfc_path.encode('utf-8'))}:")
    assert rfc8785_sha256({"path": nfc_path}) == rfc8785_sha256({"path": nfd_path})

    files = [
        (
            "src/a.py",
            "import b, a\ndef f(x):\n    return x\n",
            "import a, b\ndef f(x: int) -> int:\n    '''doc'''\n    return x\n",
        ),
        (
            "src/b.py",
            "def g(y, /):\n    t = y + 1\n    return t\n",
            "def g(z: int, /) -> int:\n    res: int = z + 1\n    return res\n",
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


def test_vararg_kwarg_and_uninitialized_annassign_in_function() -> None:
    src = "def fn(*args: int, **kwargs: str) -> None:\n    x: int\n    return None\n"
    dump = ast_canonical_dump(src, tier=1)
    assert dump is not None
