#!/usr/bin/env python3
"""
Arithmon documentation linter.

A single self-contained prose-quality gate for the Arithmon repositories,
distilled from the GIFT documentation CI. It enforces a rigour-first,
non-promotional house style across all Markdown files.

Error-level checks (these fail CI):
  - Em dashes (the character U+2014). Use a comma, a colon, or parentheses.
  - Marketing or promotional vocabulary.

Warning / info checks (reported, never fail CI):
  - Evolutionary language ("in v3.1 we improved ...").
  - Unicode notation preferences (G2 -> G2 subscript, <= -> the relation, ...).
  - Basic Markdown structure (header level jumps, very long lines).

Usage:
    python scripts/lint.py [--check] [--fix] [--verbose] [paths ...]

  --check    report only, exit 1 on any error-level issue (CI default)
  --fix      rewrite files in place to remove em dashes only
  (default)  same as --check

A machine-readable summary is written to lint_report.json.
"""

import re
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

EM_DASH = "—"  # the prohibited character
EN_DASH_AS_EM = " – "  # en dash used with spaces, treated as an em dash

# Promotional vocabulary (error). Curated to avoid domain terms that are
# legitimate in this context (exceptional Lie groups, novel connections, an
# elegant proof, a robust check). Keep this list tight and easy to tune.
MARKETING_TERMS = [
    "revolutionary", "groundbreaking", "ground-breaking",
    "game-changing", "game changer", "paradigm shift", "paradigm-shifting",
    "cutting-edge", "cutting edge", "state-of-the-art", "bleeding-edge",
    "world-class", "world class", "best-in-class", "best in class",
    "next-generation", "next generation", "next-gen",
    "unprecedented", "unparalleled", "unrivaled", "unrivalled",
    "second to none", "disruptive", "supercharge", "turbocharge",
    "seamless", "seamlessly", "effortless", "effortlessly",
    "must-have", "jaw-dropping", "mind-blowing", "mind-bending",
    "breathtaking", "blazing-fast", "lightning-fast",
    "magical", "awesome", "amazing", "incredible", "stunning",
    "the ultimate", "ultimate solution",
]

# Softer terms worth a second look (warning, never fails CI).
WATCH_TERMS = [
    "powerful", "robust", "leverage", "leverages",
    "unlock", "unlocks", "harness", "harnesses",
    "simply", "easily", "effortlessly",
]

# Evolutionary language (warning).
EVOLUTIONARY_PATTERNS = {
    r"[Ii]n\s+v\d+\.\d+": 'Avoid version-relative phrasing ("in v3.1 ..."); state current results only.',
    r"[Ww]e\s+improved": "Avoid evolutionary language; state current results only.",
    r"\b[Pp]reviously\b": "Avoid evolutionary language; state current results only.",
    r"[Uu]pdated?\s+from": "Avoid evolutionary language; state current results only.",
}

# Unicode notation preferences (info).
NOTATION_PREFERENCES = {
    r"sin\^2": "Prefer the Unicode superscript: sin² instead of sin^2.",
    r"\bG_2\b": "Prefer the Unicode subscript: G₂ instead of G_2.",
    r"\bE_8\b": "Prefer the Unicode subscript: E₈ instead of E_8.",
    r"\bK_7\b": "Prefer the Unicode subscript: K₇ instead of K_7.",
    r"\bb_2\b": "Prefer the Unicode subscript: b₂ instead of b_2.",
    r"\bb_3\b": "Prefer the Unicode subscript: b₃ instead of b_3.",
    r"<=": "Prefer the Unicode relation ≤ instead of <=.",
    r">=": "Prefer the Unicode relation ≥ instead of >=.",
    r"!=": "Prefer the Unicode relation ≠ instead of !=.",
    r"\+-": "Prefer the Unicode sign ± instead of +-.",
}


@dataclass
class Issue:
    file: str
    line: int
    column: int
    severity: str  # 'error' | 'warning' | 'info'
    category: str
    message: str
    context: str


# ---------------------------------------------------------------------------
# Checks (line-based, code blocks are skipped by the caller)
# ---------------------------------------------------------------------------

def _word_regex(term: str) -> re.Pattern:
    # Word boundaries on both sides, case-insensitive, spaces/hyphens literal.
    return re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.IGNORECASE)


def check_em_dashes(line: str, ln: int, fname: str) -> list[Issue]:
    issues = []
    for m in re.finditer(EM_DASH, line):
        issues.append(Issue(fname, ln, m.start() + 1, "error", "em-dash",
                            "Em dash found. Replace with a comma, a colon, or parentheses "
                            "(run: python scripts/lint.py --fix).", line.strip()))
    return issues


def check_marketing(line: str, ln: int, fname: str) -> list[Issue]:
    issues = []
    for term in MARKETING_TERMS:
        for m in _word_regex(term).finditer(line):
            issues.append(Issue(fname, ln, m.start() + 1, "error", "marketing",
                                f'Promotional term "{term}". Use plain, descriptive language.',
                                line.strip()))
    for term in WATCH_TERMS:
        for m in _word_regex(term).finditer(line):
            issues.append(Issue(fname, ln, m.start() + 1, "warning", "marketing",
                                f'Term "{term}" reads as promotional; consider rephrasing.',
                                line.strip()))
    return issues


def check_evolutionary(line: str, ln: int, fname: str) -> list[Issue]:
    issues = []
    for pattern, msg in EVOLUTIONARY_PATTERNS.items():
        for m in re.finditer(pattern, line):
            issues.append(Issue(fname, ln, m.start() + 1, "warning", "evolutionary", msg, line.strip()))
    return issues


def check_notation(line: str, ln: int, fname: str) -> list[Issue]:
    issues = []
    for pattern, msg in NOTATION_PREFERENCES.items():
        for m in re.finditer(pattern, line):
            # Skip if inside an inline LaTeX span ($...$).
            pre = line[:m.start()]
            if pre.count("$") % 2 == 1:
                continue
            issues.append(Issue(fname, ln, m.start() + 1, "info", "notation", msg, line.strip()))
    return issues


def check_structure(lines: list[str], fname: str) -> list[Issue]:
    issues = []
    prev_level = 0
    in_code = False
    for ln, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        h = re.match(r"^(#{1,6})\s+", line)
        if h:
            level = len(h.group(1))
            if prev_level and level > prev_level + 1:
                issues.append(Issue(fname, ln, 1, "info", "structure",
                                    f"Header level jumps from h{prev_level} to h{level}.", line.strip()))
            prev_level = level
        if len(line) > 200 and not line.lstrip().startswith("|") and "$" not in line:
            issues.append(Issue(fname, ln, 200, "info", "structure",
                                f"Very long line ({len(line)} chars).", line[:50] + "..."))
    return issues


def lint_file(path: Path, root: Path) -> list[Issue]:
    content = path.read_text(encoding="utf-8")
    fname = str(path.relative_to(root))
    lines = content.split("\n")
    issues: list[Issue] = []
    in_code = False
    for ln, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        issues += check_em_dashes(line, ln, fname)
        issues += check_marketing(line, ln, fname)
        issues += check_evolutionary(line, ln, fname)
        issues += check_notation(line, ln, fname)
    issues += check_structure(lines, fname)
    return issues


# ---------------------------------------------------------------------------
# Em-dash auto-fix (the only auto-fix; ported from the GIFT convention)
# ---------------------------------------------------------------------------

COLON_STARTERS = {
    "the", "a", "an", "it", "this", "that", "these", "those", "they", "we",
    "its", "their", "our", "for", "if", "when", "because", "since", "whether",
    "namely", "specifically", "no", "not", "only", "any", "every", "each",
}


def _fix_paired(line: str) -> str:
    m = re.search(rf"\s*{EM_DASH}\s*(.+?)\s*{EM_DASH}\s*", line)
    if not m:
        return line
    inner = m.group(1).strip()
    before, after = line[:m.start()], line[m.end():]
    sep_b = " " if before and not before.endswith(" ") else ""
    sep_a = " " if after and after[0] not in " ,.;:" else ""
    return f"{before}{sep_b}({inner}){sep_a}{after}"


def _fix_single(line: str) -> str:
    parts = re.split(rf"\s*{EM_DASH}\s*", line, maxsplit=1)
    if len(parts) != 2:
        return line
    before, after = parts[0].rstrip(), parts[1].lstrip()
    if not after:
        return line
    first = after.split()[0].lower().rstrip(".,;:")
    sep = ":" if (first in COLON_STARTERS or after[0].isupper()) else ","
    return f"{before}{sep} {after}"


def fix_content(content: str) -> str:
    out, in_code = [], False
    for line in content.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code or (EM_DASH not in line and EN_DASH_AS_EM not in line):
            out.append(line)
            continue
        line = line.replace(EN_DASH_AS_EM, f" {EM_DASH} ")
        if line.count(EM_DASH) >= 2:
            line = _fix_paired(line)
        while EM_DASH in line:
            line = _fix_single(line)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

EXCLUDE_DIRS = {".git", ".arithmon-ci", "node_modules"}


def find_markdown(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if not (EXCLUDE_DIRS & set(p.parts)))


def main() -> int:
    ap = argparse.ArgumentParser(description="Arithmon documentation linter")
    ap.add_argument("--check", action="store_true", help="report only (default)")
    ap.add_argument("--fix", action="store_true", help="remove em dashes in place")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--root", type=Path, default=None,
                    help="directory to scan (default: the repository root)")
    ap.add_argument("paths", nargs="*", type=Path)
    args = ap.parse_args()

    root = args.root.resolve() if args.root else Path(__file__).resolve().parent.parent
    files = args.paths if args.paths else find_markdown(root)

    if args.fix:
        fixed = 0
        for f in files:
            if not f.exists():
                continue
            original = f.read_text(encoding="utf-8")
            new = fix_content(original)
            if new != original:
                f.write_text(new, encoding="utf-8")
                fixed += 1
                print(f"  fixed em dashes in {f.relative_to(root)}")
        print(f"\n{fixed} file(s) rewritten." if fixed else "\nNo em dashes to fix.")
        return 0

    print("=" * 64)
    print("Arithmon documentation linter")
    print("=" * 64)
    all_issues: list[Issue] = []
    for f in files:
        if not f.exists():
            continue
        all_issues += lint_file(f, root)

    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]

    print(f"\nScanned {len(files)} file(s): "
          f"{len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info.\n")

    if errors:
        print("ERRORS (must fix):")
        for i in errors:
            print(f"  {i.file}:{i.line}:{i.column} [{i.category}] {i.message}")
            print(f"    > {i.context[:90]}")
    if warnings and args.verbose:
        print("\nWARNINGS:")
        for i in warnings:
            print(f"  {i.file}:{i.line} [{i.category}] {i.message}")
    elif warnings:
        print(f"\n{len(warnings)} warning(s) (run with --verbose to list).")

    report = {
        "summary": {"errors": len(errors), "warnings": len(warnings), "info": len(infos)},
        "issues": [i.__dict__ for i in all_issues],
    }
    (root / "lint_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    if errors:
        print("\nCI FAILED: prose errors detected.")
        return 1
    print("\nCI PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
