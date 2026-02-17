# IMOS Toolbox (Python port)

This directory contains the early-stage Python port of the IMOS Toolbox.

## Status

- Core scaffolding only.
- Parsers, preprocessing, QC, NetCDF export, and UI are not yet implemented.

## Development

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
imos-toolbox info
```
