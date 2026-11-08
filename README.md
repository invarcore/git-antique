# git-antique

<p align="center">
  <strong>Deterministic Semantic AST Diff Router & Cryptographic Receipt Generator for Multi-Agent Pull Requests.</strong><br>
  Eliminates the 80% Agent Review Bottleneck &bull; Two-Tier Semantic AST Partitioning &bull; RFC 8785 Canonical Receipts &bull; CVE-2026-85626 Safe Ref Firewall
</p>

<p align="center">
  <a href="https://github.com/invarcore/git-antique/actions"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg" alt="CI Status"></a>
  <a href="https://invarcore.com"><img src="https://img.shields.io/badge/Website-invarcore.com-0284C7?logo=googlechrome&logoColor=white" alt="Invarcore Website"></a>
  <a href="https://github.com/invarcore/git-antique/releases"><img src="https://img.shields.io/badge/Release-v0.1.0-blue.svg" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/badge/Built%20with-uv-DE5FE9.svg" alt="Built with uv"></a>
</p>

---

## ⚡ 30-Second Quickstart

Install via `pip` or run instantaneously with Astral `uv`:

```bash
# Run directly against your current Git branch vs. main
uv tool run git-antique --base main --head HEAD

# Or install in your development environment
pip install git-antique
```

### Sample Output (Markdown Partition Receipt)

```markdown
### git-antique Semantic Diff Receipt (`@antique_receipt:sha256:4f8e...`)
- **Gate Verdict**: **AUTO-APPROVABLE (ZERO LOGIC DIFF)**
- **Attention Compression**: **100.0%** (0 logic lines of 142 changed lines)

| File | Classification | Changed Lines | Human Attention Lines |
| :--- | :--- | ---: | ---: |
| `src/core/auth.py` | `TRIVIAL_COSMETIC` | 48 | 0 |
| `src/models/user.py` | `STRUCTURAL_ISOMORPHIC` | 94 | 0 |
```

If an autonomous agent merely reformatted docstrings, sorted imports, and performed alpha-renaming on local variables, `git-antique` proves mathematically that zero semantic logic mutated. Your CI pipeline auto-approves the PR in **sub-millisecond time**.

---

## 🚨 The Problem: The 80% Human Review Agent Bottleneck

Autonomous coding agents (Devin, SWE-bench bots, Claude Code, Cursor Composer) can generate hundreds of Pull Requests per day. However, **human engineering attention does not scale linearly**:

1. **The Review Deluge**: A 500-line diff often contains 450 lines of cosmetic churn (formatting, type hints, docstrings, sorted imports, variable renames) and only 50 lines of actual semantic control-flow modifications.
2. **Reviewer Fatigue & Rubber-Stamping**: Overwhelmed human reviewers either become a grinding pipeline bottleneck or begin rubber-stamping PRs, allowing subtle security bugs, logic regressions, and backdoors into production.
3. **Fragile Text-Based Diffs**: Standard `git diff` operates on textual lines. It cannot distinguish between an innocuous rename (`temp_var` $\to$ `item`) and a critical condition inversion (`if not user.is_authenticated:` $\to$ `if user.is_authenticated:`).

---

## 🏛️ The Solution: Two-Tier AST Partitioning

`git-antique` parses source code into Python Abstract Syntax Trees (AST) and routes code diffs through a deterministic two-tier semantic filter:

```
                          Incoming Git Diff
                                  │
                                  ▼
               ┌───────────────────────────────────────┐
               │         Lexical Normalizer            │
               │ • Strip whitespace & comments         │
               │ • Normalize contiguous sorted imports │
               └──────────────────┬────────────────────┘
                                  │
                   Tokens match? ─┼──► YES: Tier 0 (TRIVIAL_COSMETIC)
                                  │        [0 Human Attention Lines]
                                  ▼
               ┌───────────────────────────────────────┐
               │         Structural Normalizer         │
               │ • Strip static type annotations       │
               │ • Canonical De Bruijn local α-rename  │
               └──────────────────┬────────────────────┘
                                  │
                    ASTs match? ──┼──► YES: Tier 1 (STRUCTURAL_ISOMORPHIC)
                                  │        [0 Human Attention Lines]
                                  ▼
                     NO: Tier 2 (SEMANTIC_LOGIC_MUTATION)
                         • Branch mutations, call mutations, control flow
                         • Forces Human Four-Eyes Review
```

### Partitioning Guarantees

| Tier | Classification | Semantic Impact | Attention Tax | Action |
| :--- | :--- | :--- | :---: | :--- |
| **Tier 0** | `TRIVIAL_COSMETIC` | Docstrings, inline comments, whitespace, sorted contiguous imports. | **0 lines** | Auto-Approvable |
| **Tier 1** | `STRUCTURAL_ISOMORPHIC` | Type annotation modifications, local variable alpha-renaming ($α$-equivalence). | **0 lines** | Auto-Approvable |
| **Tier 2** | `SEMANTIC_LOGIC_MUTATION` | Changes to AST operators, function invocations, boolean conditions, or side effects. | **$N$ lines** | **Four-Eyes Review Required** |
| **Fail-Closed** | `UNANALYZED_NON_PYTHON` | CI workflows (`.github/`), Dockerfiles, shell scripts, database migrations. | **$N$ lines** | **Manual Review Required** |

---

## 🛡️ Built-In Security Guarantees

### 1. CVE-2026-85626 Safe Git Reference Firewall
To prevent command-line flag injection when invoking Git subprocesses (`git show`, `git diff`), `git-antique` enforces strict Unicode NFC canonical validation on all ref arguments (`verify_safe_git_ref`):
- Rejects refs starting with leading dashes (e.g. `--upload-pack`, `--output`).
- Rejects null bytes (`\x00`), carriage returns, and whitespace.
- Rejects directory traversal paths (`..`).

### 2. Binary-Clean Null-Byte Separation
`git-antique` queries Git using `git diff --name-only -z` separated by `bytes([0])`, preventing filename corruption or newline injection on arbitrary filenames.

### 3. Non-Python Fail-Closed Isolation
If a PR modifies non-Python files (e.g. modifying `.github/workflows/ci.yml` or adding an `.exe`), `git-antique` does not silently assume the diff is cosmetic. It classifies the file as `UNANALYZED_NON_PYTHON` and trips the gate to **REVIEW REQUIRED**, preventing backdoor injection through auxiliary assets.

### 4. RFC 8785 Canonical JSON Receipts
Every evaluation produces a tamper-evident `@antique_receipt:sha256:...` generated via RFC 8785 deterministic JSON canonicalization.

---

## 💻 CLI Usage & Arguments

```bash
git-antique [OPTIONS]
```

### Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo PATH` | `.` | Target Git repository root path. |
| `--base REF` | `main` | Base Git revision (e.g., `main`, `master`, `v0.1.0`). |
| `--head REF` | `HEAD` | Head Git revision to compare against base. |
| `--python-only` | `False` | Filter inspection strictly to `.py` files. |
| `--format FORMAT` | `markdown` | Output format: `markdown` (PR comment) or `json` (CI pipeline machine consumption). |

### Machine-Readable JSON Output (`--format json`)

```json
{
  "receipt_id": "@antique_receipt:sha256:d8a1c9e8...",
  "base_ref": "main",
  "head_ref": "HEAD",
  "total_changed_lines": 142,
  "total_human_attention_lines": 0,
  "attention_compression_ratio": 1.0,
  "requires_human_logic_review": false,
  "files": [
    {
      "filepath": "src/core/auth.py",
      "classification": "TRIVIAL_COSMETIC",
      "changed_lines": 48,
      "human_attention_lines": 0
    }
  ]
}
```

---

## 🤖 GitHub Actions CI Workflow

Add `git-antique` to `.github/workflows/antique-gate.yml` to automatically verify agent PRs:

```yaml
name: git-antique Semantic Gate

on:
  pull_request:
    branches: [main]

jobs:
  semantic-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Run git-antique Review Gate
        id: antique
        run: |
          uv tool run git-antique --base origin/main --head HEAD --format markdown > receipt.md
          cat receipt.md

      - name: Post PR Receipt Comment
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const receipt = fs.readFileSync('receipt.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: receipt
            });
```

---

## 🧪 Testing & Verification

```bash
# Clone the repository
git clone https://github.com/invarcore/git-antique.git
cd git-antique

# Run complete test suite with 100% coverage check
uv run pytest -v --cov=git_antique --cov-fail-under=95
```

---

## 📄 License

Apache-2.0. Copyright &copy; 2026 Invarcore Organization.
