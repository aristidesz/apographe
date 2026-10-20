# Collecting every day

Public data only becomes a history if you collect them every day. Apographe is a
command, so any scheduler works: cron on a server, a container on a timer, or
GitHub Actions.

## GitHub Actions

This workflow collects e-kalathi every morning and commits the new files to the
repository it runs in. Keep that repository private if the data should be.

```yaml
name: Collect data

on:
  schedule:
    - cron: "30 4 * * *" # 07:30 in Cyprus in summer
  workflow_dispatch:

permissions:
  contents: write

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install apographe
      - run: apographe run cy.ekalathi --out .
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add cy
          git commit -m "e-kalathi $(date -u +%F)" || exit 0
          git push
```

Pin the version you use (`pip install apographe==0.1.0`) so an upgrade never
surprises a scheduled run.

## cron

```cron
30 7 * * *  cd /path/to/data && apographe run cy.ekalathi --out . >> collect.log 2>&1
```
