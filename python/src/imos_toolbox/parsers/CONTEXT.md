# Parser Development Context

This file captures durable development context for parser work in
`python/src/imos_toolbox/parsers/`.

Use this as the implementation guide. Use `PARSER_PARITY.md` as the parity/status ledger.

## Current Snapshot

- Parser suite status (latest run): `260 passed, 108 skipped, 0 failed`
- Static analysis: `ruff` clean · `mypy src/imos_toolbox/parsers` clean (0 errors)
- Fully ported parsers: 31 (all MATLAB `*Parse.m` entry points)
- Stub parsers: 0
- Note: SBE37SM and SBE56 are covered indirectly via the shared SeaBird suite; no dedicated test files yet.
- InfinitySD `_fix_repeated_times_jfe()` is an exact port of `fixRepeatedTimesJFE.m`, including the truncated first/last burst alignment (validated against the MATLAB worked example).
- Aquadopp Profiler exposes the decoded `power_level` metadata attribute (`TimCtrlReg` bits 7:6).

## Parser Contract and Conventions

1. Every parser subclasses `BaseParser` and implements:
   - `parser_name: str`
   - `parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset`
2. Validate input file count/extension early and raise explicit `ValueError` on invalid input.
3. Build datasets with `IMOSDataset` helpers:
   - `add_dimension(...)` for coordinates (usually `TIME`)
   - `add_variable(...)` for data/scaffold variables
4. For time-series style datasets, follow scaffold convention:
   - `TIMESERIES` scalar `np.int32(1)`
   - `LATITUDE`, `LONGITUDE` scalar NaN (`np.float64`)
   - `NOMINAL_DEPTH` scalar NaN (`np.float32`)
5. For geophysical variables, keep `coordinates` attr consistent:
   - `"TIME LATITUDE LONGITUDE NOMINAL_DEPTH"` (or parser-specific dim order where required)
6. Set core dataset attrs consistently:
   - `toolbox_input_file`, `featureType`, `instrument_make`, `instrument_model`,
     `instrument_serial_no`, `parser`, `source_format`

## MATLAB Porting Rules

1. Port behavior, not just format acceptance.
2. Preserve MATLAB unit conversions, offsets, and timing semantics.
3. Preserve IMOS variable naming conventions already used in this codebase.
4. Keep parser-specific edge-case handling explicit (no silent fallback).
5. If MATLAB uses datenum-style time, keep conversion logic faithful and tested.

## Test Expectations (per parser)

Each parser test module under `tests/parsers/` should cover:

1. Parser instantiation and `parser_name`.
2. Format validation failure paths.
3. Parse smoke test on real fixtures when available.
4. Dimension/schema assertions (`TIME`, parser-specific dims).
5. IMOS scaffold checks and coordinates attributes.
6. Metadata assertions.
7. Parser-specific behavior assertions (e.g., QC behavior, repeated-time correction, profile split).

When canonical fixtures are not available, use deterministic synthetic fixtures in `tmp_path`
and keep assertions tied to MATLAB-equivalent behavior.

## Development Workflow for New/Updated Parsers

1. Read MATLAB source (`Parser/*Parse.m` + helper functions it calls).
2. Implement/update Python parser module in `src/imos_toolbox/parsers/`.
3. Ensure parser export is wired in `src/imos_toolbox/parsers/__init__.py`.
4. Keep CLI parser registration lists in `src/imos_toolbox/cli.py` in sync where applicable.
5. Add/replace tests in `tests/parsers/test_<parser>.py`.
6. Update `src/imos_toolbox/parsers/PARSER_PARITY.md`:
   - parser section status
   - table rows if coverage changed
   - generated footer snapshot after running parser suite

## Validation Commands

Run from `python/`:

```bash
uv run ruff check src/imos_toolbox/parsers/<parser_file>.py tests/parsers/test_<parser>.py
uv run mypy src/imos_toolbox/parsers/<parser_file>.py --follow-imports=skip
uv run pytest -q tests/parsers/test_<parser>.py
uv run pytest -q tests/parsers
```

Use the final parser-suite output as the parity snapshot source.

## Recent Parser Decisions (2026-06-29)

- `nxic.py`, `echoview.py`, and `infinity_sd.py` are fully implemented (no longer stubs).
- `test_nxic.py`, `test_echoview.py`, and `test_infinity_sd.py` are functional coverage suites.
- Echoview currently relies on synthetic fixtures (no canonical real Echoview fixture in repo).
- InfinitySD includes repeated-time correction aligned with MATLAB `fixRepeatedTimesJFE` intent.

