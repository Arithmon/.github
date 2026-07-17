# Contributing

Thank you for your interest in the Arithmon program.

## Scope

Arithmon is the program: the durable hypothesis. GIFT is its founding framework.
Most concrete code and proofs live in the framework repositories under
github.com/Arithmon. This organization holds program-level material.

This is a research program, not a product, so the useful contributions are not
the usual ones. A sharp objection helps more than a typo fix.

## What helps

- A **counterexample, a refuted route, or a failed prediction**, stated
  precisely enough to be checked. Negative results are first-class here: the
  open problems list them as theorems about the territory.
- A **flaw in the methodology**: a null model that is too weak, a grammar that
  smuggles in a free parameter, a calibration case that should change the
  verdict, a look-elsewhere correction we missed.
- A **rival or hostile framework** to run through the Sieve, including ones
  built to make the test fail.
- A **neighbouring body of work** we have not mapped, with the precise delta to
  Arithmon (what we do that it does not, and the reverse).
- A reproduction: an independent re-run of a certified count or a frozen score.

## What does not help

- Tuning anything to data. The program never fits; a contribution that fits is
  off-topic by construction.
- Asking us to revise a frozen prediction after the relevant data arrived.
- Adding constants to the algebraic vocabulary to make a relation land. The
  vocabulary is closed and public; widening it silently is the failure mode the
  Sieve exists to catch.
- Promotional rewording, hype, or rank-claiming. The house style forbids it and
  the linter enforces it.

## Forms of contribution

Each procedure lives in the repository that owns it:

| You want to | Go to |
|-------------|-------|
| Propose an Atlas entry (a neighbouring work) | [Atlas / CONTRIBUTING](https://github.com/arithmon/atlas/blob/main/CONTRIBUTING.md) |
| Propose or attack a null model | [Sieve / CONTRIBUTING](https://github.com/arithmon/sieve/blob/main/CONTRIBUTING.md) |
| Submit a hostile or rival framework to the Sieve | [Sieve / CONTRIBUTING](https://github.com/arithmon/sieve/blob/main/CONTRIBUTING.md) |
| Report a possible cherry-picking issue | [Sieve / CONTRIBUTING](https://github.com/arithmon/sieve/blob/main/CONTRIBUTING.md) |
| Challenge a frozen prediction or a freeze | [Program / CONTRIBUTING](https://github.com/arithmon/program/blob/main/CONTRIBUTING.md) |
| Propose or attack an open problem | [Program / CONTRIBUTING](https://github.com/arithmon/program/blob/main/CONTRIBUTING.md) |
| Contribute a certified count or a proof | [Lean / CONTRIBUTING](https://github.com/arithmon/lean/blob/main/CONTRIBUTING.md) |

When in doubt, open an issue on the most relevant repository and say plainly
what you are claiming and how it could be checked.

## House style

Documents follow a rigour-first, non-promotional style, enforced by a small
linter that lives in the `arithmon/.github` repository (`scripts/lint.py`):

- No em dashes. Use a comma, a colon, or parentheses.
- No marketing or promotional vocabulary. Describe, do not advertise.
- Prefer Unicode notation (G₂, K₇, E₈, ≤) over ASCII substitutes.
- State current results. Avoid version-relative phrasing.

From a clone of `arithmon/.github` you can run it directly:

```
python scripts/lint.py --check --verbose
python scripts/lint.py --fix          # removes em dashes only
```

## Continuous integration

Any repository in this organization can opt into the same prose gate by calling
the shared workflow:

```yaml
jobs:
  lint:
    uses: arithmon/.github/.github/workflows/lint-reusable.yml@main
```
