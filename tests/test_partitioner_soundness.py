# Copyright 2026 Invarcore Organization
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for P0-4 (Docstring Decorator Pin) and P0-5 (Reflection Guard) soundness."""

from git_antique.partitioner import classify_python_file_diff


def test_p0_4_mcp_tool_docstring_mutation_escalates_to_semantic() -> None:
    prefixes = [
        "@mcp.tool()",
        "@server.tool",
        "@tool",
        "@click.command()",
        "@app.get('/items')",
        "@router.post('/login')",
        "@FastMCP.tool()",
    ]
    for dec in prefixes:
        before = f"{dec}\ndef handle_req(param: int) -> int:\n    '''Original schema description.'''\n    return param * 2\n"
        after = f"{dec}\ndef handle_req(param: int) -> int:\n    '''Mutated schema description (ETUDE vector).'''\n    return param * 2\n"
        verdict = classify_python_file_diff("src/tool.py", before, after)
        assert verdict.classification == "SEMANTIC_LOGIC_MUTATION", f"Failed for decorator {dec}"
        assert verdict.reason == "P0-4: docstring mutation on schema-bound decorated function"
        assert verdict.human_attention_lines == verdict.changed_lines


def test_p0_4_undecorated_and_non_schema_docstring_mutation_stays_cosmetic() -> None:
    # Undecorated function docstring update is cosmetic
    before = "def internal_helper(x: int) -> int:\n    '''Helper v1.'''\n    return x + 1\n"
    after = "def internal_helper(x: int) -> int:\n    '''Helper v2.'''\n    return x + 1\n"
    verdict = classify_python_file_diff("src/helper.py", before, after)
    assert verdict.classification == "TRIVIAL_COSMETIC"
    assert verdict.human_attention_lines == 0

    # Non-schema decorator (e.g., @staticmethod, @property) docstring update is cosmetic
    before_static = "@staticmethod\ndef util(y):\n    '''Util v1.'''\n    return y\n"
    after_static = "@staticmethod\ndef util(y):\n    '''Util v2.'''\n    return y\n"
    verdict_static = classify_python_file_diff("src/util.py", before_static, after_static)
    assert verdict_static.classification == "TRIVIAL_COSMETIC"


def test_p0_4_schema_bound_function_whitespace_and_comments_stay_cosmetic() -> None:
    before = "@mcp.tool()\ndef compute(val: int) -> int:\n    '''Fixed docstring.'''\n    # Comment A\n    return val * 2\n"
    after = "@mcp.tool()\ndef compute(val: int) -> int:\n    '''Fixed docstring.'''\n    # Comment B with formatting\n    return val   *   2\n"
    verdict = classify_python_file_diff("src/tool.py", before, after)
    assert verdict.classification == "TRIVIAL_COSMETIC"
    assert verdict.human_attention_lines == 0


def test_p0_5_reflection_guard_escalates_local_alpha_rename() -> None:
    reflection_calls = [
        "locals()",
        "vars()",
        "dir()",
        "eval('item + 1')",
        "exec('print(item)')",
        "getattr(obj, 'item')",
        "setattr(obj, 'item', 1)",
    ]
    for ref_call in reflection_calls:
        before = f"def handle_data(items, /):\n    item = items[0]\n    {ref_call}\n    return item\n"
        after = f"def handle_data(items, /):\n    renamed_item = items[0]\n    {ref_call}\n    return renamed_item\n"
        verdict = classify_python_file_diff("src/handler.py", before, after)
        assert verdict.classification == "SEMANTIC_LOGIC_MUTATION", f"Failed for reflection call {ref_call}"
        assert verdict.reason == "P0-5: local alpha-renaming blocked due to runtime reflection call"
        assert verdict.human_attention_lines == verdict.changed_lines


def test_p0_5_pure_function_alpha_rename_stays_isomorphic() -> None:
    before = "def pure_compute(items, /):\n    total = 0\n    for val in items:\n        total += val\n    return total\n"
    after = "def pure_compute(items, /):\n    running_sum = 0\n    for val in items:\n        running_sum += val\n    return running_sum\n"
    verdict = classify_python_file_diff("src/calc.py", before, after)
    assert verdict.classification == "STRUCTURAL_ISOMORPHIC"
    assert verdict.human_attention_lines == 0


def test_p0_5_reflection_function_without_rename_stays_isomorphic_or_cosmetic() -> None:
    before = "def inspect_scope(items, /):\n    total = 0\n    eval('total + 1')\n    return total\n"
    after = "def inspect_scope(items: list, /) -> int:\n    total: int = 0\n    eval('total + 1')\n    return total\n"
    verdict = classify_python_file_diff("src/calc.py", before, after)
    assert verdict.classification == "STRUCTURAL_ISOMORPHIC"
    assert verdict.human_attention_lines == 0
