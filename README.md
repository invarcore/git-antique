# git-antique

Deterministic Two-Tier Semantic AST Diff Router and RFC 8785 Receipt Generator for Autonomous Multi-Agent Pull Requests.

## Overview

Addresses the 80% human-review agent idle bottleneck exposed in frontier AI software engineering workflows. `git-antique` partitions code diffs into:
- **Tier 0 (TRIVIAL_COSMETIC)**: Docstrings, comments, whitespace, and sorted contiguous imports (0 human attention lines).
- **Tier 1 (STRUCTURAL_ISOMORPHIC)**: Type annotation stripping and local De Bruijn alpha-renaming (0 human attention lines).
- **Tier 2 (SEMANTIC_LOGIC_MUTATION)**: AST logic, branch, operator, or external function call alterations requiring human four-eyes verification.

Produces cryptographically signed RFC 8785 canonical receipts (`@antique_receipt:sha256:...`) with deterministic attention compression ratios.

## Testing

```bash
uv run pytest tests/test_partitioner.py -v --cov=git_antique --cov-fail-under=95
```

## License

Apache-2.0
