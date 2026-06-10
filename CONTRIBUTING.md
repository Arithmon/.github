# Contributing

Thank you for your interest in the Arithmon program.

## Scope

Arithmon is the program: the durable hypothesis. GIFT is its founding framework.
Most concrete code and proofs live in the framework repositories under
github.com/gift-framework. This organization holds program-level material.

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
