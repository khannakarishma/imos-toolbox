# IMOS Toolbox (Python port)

This directory contains the early-stage Python port of the IMOS Toolbox.

## Status

- Core scaffolding only.
- Parsers, preprocessing, QC, NetCDF export, and UI are not yet implemented.

## Development

```bash
cd python
python -m pip install uv
uv python install 3.14
uv venv --python 3.14 .venv
uv sync --extra dev
uv run imos-toolbox info

# Verify runtime
uv run python --version

# Tests, lint, type checking
uv run pytest -v
uv run ruff check src tests
uv run mypy src

# Resolve parser mapping from existing instruments table
uv run imos-toolbox parser-map --make "SEABIRD" --model "SBE19plus V2" --repo-root ..

# Parse one SBE19 .cnv file (initial support)
uv run imos-toolbox parse-sbe19 --file /path/to/file.cnv --mode timeSeries

# Parse one SBE26 .tid file (initial support)
uv run imos-toolbox parse-sbe26 --file /path/to/file.tid --mode timeSeries

# Parse one SBE37 .asc/.cnv file (initial support)
uv run imos-toolbox parse-sbe37 --file /path/to/file.asc --mode timeSeries

# Parse one SBE37SM .asc/.cnv file (initial support)
uv run imos-toolbox parse-sbe37sm --file /path/to/file.cnv --mode timeSeries

# Parse one SBE39 .asc file (initial support)
uv run imos-toolbox parse-sbe39 --file /path/to/file.asc --mode timeSeries

# Parse one SBE56 .cnv/.csv file (initial support)
uv run imos-toolbox parse-sbe56 --file /path/to/file.csv --mode timeSeries

# Parse one WQM .dat/.raw file (initial support)
uv run imos-toolbox parse-wqm --file /path/to/file.dat --mode timeSeries

# Parse one WetStar .raw file (+ matching .dev)
uv run imos-toolbox parse-wetstar --file /path/to/file.raw --mode timeSeries

# Parse one ECOTriplet .raw file (+ matching .dev)
uv run imos-toolbox parse-ecotriplet --file /path/to/file.raw --mode timeSeries

# Parse one ECOBB9 .raw file (+ matching .dev)
uv run imos-toolbox parse-ecobb9 --file /path/to/file.raw --mode timeSeries

# Parse one DR1050 export file (initial support)
uv run imos-toolbox parse-dr1050 --file /path/to/file.txt --mode timeSeries
```

## Command Shortcuts

Use the Makefile shortcuts to run all tooling consistently through `uv run`:

```bash
cd python
make info
make test
make lint
make typecheck
make lock-check
```

## Troubleshooting

- Wrong Python version: run `uv run python --version`; recreate env with `uv venv --python 3.14 .venv`.
- Stale environment: remove and rebuild with `rm -rf .venv && uv venv --python 3.14 .venv && uv sync --extra dev`.
- Lock mismatch after dependency edits: run `uv lock` and commit `uv.lock`.
