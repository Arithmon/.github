#!/usr/bin/env python3
"""
Arithmon cross-repo sync watch.

Checks that the public faces of the Arithmon repositories stay synchronized:
GitHub descriptions present, the canonical footer in place, sibling
cross-links intact, and the freeze facts (DOI, freeze version) consistent
with the Sieve README, which is their source of truth. When the Sieve cuts a
new freeze version, every stale mention elsewhere becomes a reported drift:
this check is the propagation reminder.

Read-only by design: it reports drift, it never edits. Fixing is a
deliberate, logged act (charter rule: no silent edits).

Usage:
    python3 scripts/sync_check.py [--report report.md]

Exit code 0 = in sync, 1 = drift detected, 2 = fetch failure.
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ---------------------------------------------------------------------------
# What is watched. Adding a file (a future CHANGELOG.md, a new repo) is one
# line here; adding an invariant is one entry in the check tables below.
# ---------------------------------------------------------------------------

FILES = {
    "profile": ("Arithmon/.github", "profile/README.md"),
    "program": ("Arithmon/Program", "README.md"),
    "program_problem": ("Arithmon/Program", "problems/coincidence-methodology.md"),
    "atlas": ("Arithmon/Atlas", "README.md"),
    "sieve": ("Arithmon/Sieve", "README.md"),
    "hub": ("gift-framework/gift-framework", "README.md"),
    "gift": ("gift-framework/GIFT", "README.md"),
    "core": ("gift-framework/core", "README.md"),
}

# Repositories that must carry a non-empty GitHub description.
DESCRIBED_REPOS = ["Arithmon/.github", "Arithmon/Program", "Arithmon/Atlas", "Arithmon/Sieve"]

FOOTER = "GIFT is the founding framework of the Arithmon program"

# file key -> list of (label, case-insensitive substring) that must appear.
REQUIRED = {
    "profile": [
        ("link to Program", "github.com/arithmon/program"),
        ("link to Atlas", "github.com/arithmon/atlas"),
        ("link to Sieve", "github.com/arithmon/sieve"),
        ("link to GIFT docs", "github.com/gift-framework/gift"),
        ("link to Lean core", "github.com/gift-framework/core"),
    ],
    "program": [
        ("canonical footer", FOOTER),
        ("link to Atlas", "github.com/arithmon/atlas"),
        ("link to Sieve", "github.com/arithmon/sieve"),
    ],
    "atlas": [
        ("canonical footer", FOOTER),
        ("link to Program", "github.com/arithmon/program"),
        ("link to Sieve", "github.com/arithmon/sieve"),
    ],
    "sieve": [
        ("canonical footer", FOOTER),
        ("link to Program", "github.com/arithmon/program"),
        ("link to Atlas", "github.com/arithmon/atlas"),
    ],
    "hub": [("Arithmon program banner", "arithmon program")],
    "gift": [("Arithmon program banner", "arithmon program")],
    "core": [("Arithmon program banner", "arithmon program")],
}

DOI_RE = re.compile(r"10\.5281/zenodo\.\d+")
FREEZE_RE = re.compile(r"[Ff]reeze v(\d+\.\d+)")

# Files whose Zenodo DOIs and freeze-version mentions must all be declared in
# the Sieve README (the source of truth). GIFT-side Zenodo DOIs live outside
# this rule on purpose: only Arithmon-org files are held to it.
SIEVE_FACT_CONSUMERS = ["profile", "program", "program_problem", "atlas"]


def fetch_raw(repo, path):
    url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_description(repo):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return (json.load(r).get("description") or "").strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="also write the markdown report here")
    args = parser.parse_args()

    drift, fetch_errors = [], []

    contents = {}
    for key, (repo, path) in FILES.items():
        try:
            contents[key] = fetch_raw(repo, path)
        except Exception as exc:
            fetch_errors.append(f"could not fetch `{repo}/{path}`: {exc}")

    for repo in DESCRIBED_REPOS:
        try:
            if not fetch_description(repo):
                drift.append(f"`{repo}` has no GitHub description.")
        except Exception as exc:
            fetch_errors.append(f"could not read description of `{repo}`: {exc}")

    for key, rules in REQUIRED.items():
        text = contents.get(key)
        if text is None:
            continue
        repo, path = FILES[key]
        lowered = text.lower()
        for label, needle in rules:
            if needle.lower() not in lowered:
                drift.append(f"`{repo}/{path}`: missing {label} (`{needle}`).")

    sieve = contents.get("sieve")
    if sieve is not None:
        sieve_dois = set(DOI_RE.findall(sieve))
        sieve_versions = set(FREEZE_RE.findall(sieve))
        for key in SIEVE_FACT_CONSUMERS:
            text = contents.get(key)
            if text is None:
                continue
            repo, path = FILES[key]
            for doi in DOI_RE.findall(text):
                if doi not in sieve_dois:
                    drift.append(
                        f"`{repo}/{path}` cites DOI `{doi}`, "
                        f"not declared in the Sieve README (stale freeze reference?)."
                    )
            for version in FREEZE_RE.findall(text):
                if sieve_versions and version not in sieve_versions:
                    drift.append(
                        f"`{repo}/{path}` mentions freeze v{version}, "
                        f"the Sieve README declares {sorted(sieve_versions)}."
                    )

    lines = ["# Arithmon sync watch report", ""]
    if not drift and not fetch_errors:
        lines.append("All invariants pass. Repositories are in sync.")
    if drift:
        lines.append(f"**{len(drift)} drift item(s):**")
        lines += [f"- [ ] {item}" for item in drift]
    if fetch_errors:
        lines.append("")
        lines.append(f"**{len(fetch_errors)} fetch problem(s)** (not drift, retry or investigate):")
        lines += [f"- {item}" for item in fetch_errors]
    report = "\n".join(lines) + "\n"

    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)

    if drift:
        return 1
    if fetch_errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
