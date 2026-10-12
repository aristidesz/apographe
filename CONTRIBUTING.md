# Contributing

New sources, fixes and ideas are all welcome. For anything bigger than a small
fix, open an issue first so we can agree on the approach.

## Set up

You need [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/aristidesz/apographe.git
cd apographe
uv sync --all-extras
uv run pre-commit install
```

## Check your change

```bash
uv run pytest            # tests run offline, against trimmed real responses
uv run ruff check        # lint
uv run ruff format       # format
uv run mypy              # types
```

CI runs the same checks on Python 3.11 to 3.13 for every pull request.

## Workflow

1. Branch from `main` with a name that says what it does, such as
   `fix/fuel-missing-area` or `feature/gr-ekatanalotis`.
2. Open a pull request into `main`. CI must pass before it merges.
3. Releases are tags on `main` (`v0.2.0`). Pushing one publishes that version
   to PyPI.

Adding a source? [This guide](docs/adding-a-source.md) shows the whole class in
about 30 lines.
