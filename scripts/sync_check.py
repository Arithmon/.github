#!/usr/bin/env python3
"""
Arithmon cross-repo sync watch.

Checks that the public faces of the Arithmon program stay synchronized:
GitHub descriptions present, the canonical footer in place, sibling
cross-links intact, and the freeze facts (DOI, freeze version) consistent
with the Sieve README and the program ledger, which are their source of
truth. When the Sieve cuts a new freeze version, every stale mention
elsewhere becomes a reported drift: this check is the propagation reminder.

The deployed front door at arithmon.com is watched alongside the READMEs.
It is uploaded rather than committed, so it is read as served: a page that
drifts from the repositories is the drift most readers meet first.

Read-only by design: it reports drift, it never edits. Fixing is a
deliberate, logged act (charter rule: no silent edits).

Usage:
    python3 scripts/sync_check.py [--report report.md]

Exit code 0 = in sync, 1 = drift detected, 2 = fetch failure.
"""

import argparse
import html
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
    "lean": ("Arithmon/Lean", "README.md"),
    "hub": ("gift-framework/gift-framework", "README.md"),
    "gift": ("Arithmon/K7", "README.md"),
    "core": ("Arithmon/K7-Lean", "README.md"),
}

# Deployed pages watched at their public URL rather than in git. The program's
# front door is a claim surface like any README, but it is uploaded, not
# committed: reading what is actually served is the only way to hold it to the
# same invariants. A page that drifts from the repos is the drift that the
# most readers see first.
SITES = {
    "site": "https://arithmon.com/",
}

# Repositories that must carry a non-empty GitHub description.
DESCRIBED_REPOS = ["Arithmon/.github", "Arithmon/Program", "Arithmon/Atlas", "Arithmon/Sieve", "Arithmon/Lean"]

# Declared DOIs live in two registers: the Sieve README owns the freeze facts,
# and the program ledger owns every DOI used anywhere in the org.
LEDGER = ("Arithmon/Program", "LEDGER.json")

FOOTER = "K₇ (formerly GIFT) is the founding framework of the Arithmon program"

# file key -> list of (label, case-insensitive substring) that must appear.
REQUIRED = {
    "profile": [
        ("link to Program", "github.com/arithmon/program"),
        ("link to Atlas", "github.com/arithmon/atlas"),
        ("link to Sieve", "github.com/arithmon/sieve"),
        ("link to Lean", "github.com/arithmon/lean"),
        ("link to K7 docs", "github.com/arithmon/k7"),
        ("link to Lean core", "github.com/arithmon/k7-lean"),
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
    "lean": [
        ("canonical footer", FOOTER),
        ("link to Program", "github.com/arithmon/program"),
        ("link to Atlas", "github.com/arithmon/atlas"),
        ("link to Sieve", "github.com/arithmon/sieve"),
    ],
    "hub": [("Arithmon program banner", "arithmon program")],
    "gift": [("Arithmon program banner", "arithmon program")],
    "core": [("Arithmon program banner", "arithmon program")],
    "site": [
        ("canonical footer", FOOTER),
        ("link to Program", "github.com/arithmon/program"),
        ("link to Atlas", "github.com/arithmon/atlas"),
        ("link to Sieve", "github.com/arithmon/sieve"),
        ("link to Lean", "github.com/arithmon/lean"),
        ("link to K7", "github.com/arithmon/k7"),
        ("link to Lean core", "github.com/arithmon/k7-lean"),
    ],
}

DOI_RE = re.compile(r"10\.5281/zenodo\.\d+")
FREEZE_RE = re.compile(r"[Ff]reeze v(\d+\.\d+)")

# Files whose Zenodo DOIs and freeze-version mentions must all be declared,
# either in the Sieve README (freeze facts, its own source of truth) or in the
# program ledger (every DOI the org uses). A DOI in neither register is an
# undeclared claim: a stale freeze reference, or a superseded version DOI
# where the concept DOI was meant. GIFT-side DOIs quoted inside papers live
# outside this rule on purpose: only these surfaces are held to it.
SIEVE_FACT_CONSUMERS = ["profile", "program", "program_problem", "atlas", "site"]


def fetch_raw(repo, path):
    url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_page(url):
    # Entities are resolved so that a footer written as `K&#8327;` matches the
    # same invariant as a footer written as `K₇`. Tags are left in place: the
    # link rules read the hrefs.
    req = urllib.request.Request(url, headers={"User-Agent": "arithmon-sync-check"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return html.unescape(r.read().decode("utf-8"))


def surface_label(key):
    if key in SITES:
        return SITES[key]
    repo, path = FILES[key]
    return f"{repo}/{path}"


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

    for key, url in SITES.items():
        try:
            contents[key] = fetch_page(url)
        except Exception as exc:
            fetch_errors.append(f"could not fetch `{url}`: {exc}")

    ledger_dois = set()
    try:
        ledger_dois = set(json.loads(fetch_raw(*LEDGER)).get("known_dois", {}))
    except Exception as exc:
        fetch_errors.append(f"could not read the ledger `{LEDGER[0]}/{LEDGER[1]}`: {exc}")

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
        where = surface_label(key)
        lowered = text.lower()
        for label, needle in rules:
            if needle.lower() not in lowered:
                drift.append(f"`{where}`: missing {label} (`{needle}`).")

    sieve = contents.get("sieve")
    if sieve is not None:
        sieve_dois = set(DOI_RE.findall(sieve))
        declared_dois = sieve_dois | ledger_dois
        sieve_versions = set(FREEZE_RE.findall(sieve))
        for key in SIEVE_FACT_CONSUMERS:
            text = contents.get(key)
            if text is None:
                continue
            where = surface_label(key)
            for doi in DOI_RE.findall(text):
                if doi not in declared_dois:
                    drift.append(
                        f"`{where}` cites DOI `{doi}`, declared neither in the "
                        f"Sieve README nor in the program ledger "
                        f"(stale freeze reference, or a version DOI where the "
                        f"concept DOI was meant?)."
                    )
            for version in FREEZE_RE.findall(text):
                if sieve_versions and version not in sieve_versions:
                    drift.append(
                        f"`{where}` mentions freeze v{version}, "
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
