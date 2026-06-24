# Python Port Development Guide

## Important Instructions

**⚠️ DO NOT CREATE NEW DOCUMENTATION FILES** - Only create documents when explicitly requested by the user. Share summaries, results, and information directly in chat responses instead of creating new .md files.

**⚠️ MATLAB CODE IS IMMUTABLE** - The MATLAB code is the authoritative reference and MUST NOT be changed. The Python code MUST reflect ALL functionalities of the MATLAB version exactly (bug-for-bug parity where applicable). The Python code should be as modular or MORE modular than the MATLAB version — use clear separation of concerns (thin parser classes delegating to shared utility modules, base classes, helper functions). Every feature, conversion, metadata field, edge case, and variable produced by the MATLAB parser must be reproduced in the Python port.

## Migration Context

The IMOS Toolbox is undergoing an active migration from MATLAB to Python. The Python implementation lives under `python/` and aims to provide feature parity with the legacy MATLAB codebase while modernizing the architecture.

**Current Status**: Phase 6 complete (end-to-end pipeline operational). Active work on Phase 7 (Dash UI) and Phase 10 (regression testing).

**Key Documents**:
- `python/docs/ROADMAP.md` - Comprehensive migration checklist and progress tracking
- `python/docs/PARSER_FORMAT_MATRIX.md` - Parser implementation status
- `python/docs/SCHEMA.md` - Deployment database schema documentation
- `python/docs/MCR_REGRESSION_PLAN.md` - Regression testing strategy (recommended approach)

## Development Workflow

### Environment Setup (UV-First)
```bash
cd python
python -m pip install uv
uv python install 3.14
uv venv --python 3.14 .venv
uv sync --extra dev
```

### Daily Development Commands
```bash
# Verify environment
uv run python --version              # Should report 3.14.x
uv run imos-toolbox info            # Verify package entrypoint

# Run tests
uv run pytest -v                    # Full test suite
uv run pytest tests/parsers/        # Specific test directory

# Code quality
uv run ruff check src tests         # Lint
uv run ruff format src tests        # Format
uv run mypy src                     # Type check

# CLI usage
uv run imos-toolbox parse-sbe37 --file data.asc --mode timeSeries
uv run imos-toolbox process --file raw.asc --output-dir out --mode timeSeries --parser sbe37

# Launch Dash UI
uv sync --extra ui --extra dev
uv run imos-toolbox ui --host 127.0.0.1 --port 8050
```

### Makefile Shortcuts
```bash
make test                           # Run pytest
make lint                           # Run ruff
make typecheck                      # Run mypy
make lock-check                     # Verify uv.lock is synced
```

## Architecture Patterns

### Parser Implementation
**Location**: `python/src/imos_toolbox/parsers/`

**Pattern**: Each parser inherits from `BaseParser` and implements `parse(file_paths, mode) → IMOSDataset`

**Key Conventions**:
- One parser class per instrument family (e.g., `SBE37Parser`, `VemcoParser`)
- Use xarray as the underlying data model wrapper (`IMOSDataset` wraps `xr.Dataset`)
- Handle TIME coordinate conversion to MATLAB datenum format for consistency
- Support both `timeSeries` and `profile` modes where applicable
- Validate file extensions in parser (raise `ValueError` for wrong formats)
- Register parser in `__init__.py` with CLI command mapping

**Example Structure**:
```python
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.model import IMOSDataset

class MyInstrumentParser(BaseParser):
    def parse(self, file_paths: list[str], mode: str) -> IMOSDataset:
        # Validate inputs
        # Parse instrument file(s)
        # Build xarray Dataset
        # Wrap in IMOSDataset
        return IMOSDataset(ds)
```

**Testing Pattern**:
```python
# tests/parsers/test_myinstrument.py
def test_basic_parse(tmp_path):
    # Create synthetic test file
    test_file = tmp_path / "test.dat"
    test_file.write_text("...")
    
    # Parse and verify
    parser = MyInstrumentParser()
    dataset = parser.parse([str(test_file)], "timeSeries")
    
    assert "TEMP" in dataset.variables
    assert dataset.TIME.size > 0
```

### Preprocessing Routines
**Location**: `python/src/imos_toolbox/preprocessing/routines/`

**Pattern**: Each routine inherits from `PPRoutine` and implements `process(dataset) → PPResult`

**Key Conventions**:
- Use base class `PPRoutine` for preprocessing transformations
- Return `PPResult` with modified dataset and log messages
- Chain execution via `run_pp_chain(dataset, routines, mode)`
- Default chains defined for `timeSeries` and `profile` modes
- Use `gsw` library for oceanographic calculations (note API differences from MATLAB gsw)

**Common Routines**:
- `pressureRelPP` - Convert absolute to relative pressure
- `depthPP` - Calculate depth from pressure using gsw
- `salinityPP` - Calculate salinity from conductivity, temperature, pressure
- `oxygenPP` - Convert oxygen sensor outputs
- `velocityMagDirPP` - Calculate current speed/direction from U/V components

### Automatic QC Routines
**Location**: `python/src/imos_toolbox/autoqc/routines/`

**Pattern**: Inherit from `QCVariableRoutine` (single variable) or `QCSetRoutine` (multi-variable)

**Key Conventions**:
- Use `QCFlags` enum (GOOD=1, PROBABLY_GOOD=2, PROBABLY_BAD=3, BAD=4, MISSING=9)
- **Flag upgrade-only semantics**: Never downgrade existing QC flags
- Return `QCResult` with updated flags and log messages
- Chain execution via `run_qc_chain(dataset, routines, mode)`
- Default chains defined for `timeSeries` and `profile` modes

**QC Routine Types**:
- **Variable routines** (`QCVariableRoutine`): Operate on individual variables (e.g., `GlobalRangeQC`)
- **Set routines** (`QCSetRoutine`): Operate across multiple variables (e.g., `DensityInversionSetQC`)

**Testing Pattern**:
```python
def test_qc_routine():
    # Create synthetic dataset with known issues
    ds = create_test_dataset()
    
    # Run QC routine
    routine = MyQCRoutine()
    result = routine.run(ds, "TEMP", "timeSeries")
    
    # Verify flags upgraded correctly
    assert result.flags[0] == QCFlags.BAD
    assert result.flags[1] == QCFlags.GOOD
```

### NetCDF Export
**Location**: `python/src/imos_toolbox/export/`

**Key Conventions**:
- Use template files from `NetCDF/template/` for attribute definitions
- Token syntax: `[mat ...]` for Python eval (was MATLAB eval)
- Apply IMOS conventions (CF-1.6, IMOS-1.4)
- Enable compression by default (zlib level 4)
- Export one NetCDF per instrument

## Code Style and Quality Gates

### Required Checks Before Commit
1. **All tests pass**: `uv run pytest -v`
2. **Ruff clean**: `uv run ruff check src tests`
3. **Mypy clean**: `uv run mypy src` (for typed modules)

### Naming Conventions
- **Modules**: `snake_case` (e.g., `sbe37.py`, `global_range_qc.py`)
- **Classes**: `PascalCase` (e.g., `SBE37Parser`, `GlobalRangeQC`)
- **Functions**: `snake_case` (e.g., `parse_template`, `run_qc_chain`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `QC_FLAGS`, `DEFAULT_CHAIN`)

### Docstring Style
Use Google-style docstrings:
```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When validation fails
    """
```

## Regression Testing Strategy

### MCR-Based Approach (Recommended)
Use MATLAB Component Runtime (MCR v95) for regression testing against MATLAB outputs without requiring MATLAB licenses.

**Key Benefits**:
- No MATLAB license cost ($10,750+ savings)
- Faster implementation (6 weeks vs 10 weeks)
- CI/CD friendly

**Documentation**: See `python/docs/MCR_REGRESSION_PLAN.md` for detailed strategy

### Test Categories
1. **Parser tests**: Compare parsed variables, dimensions, metadata
2. **Preprocessing tests**: Compare transformed data values (gsw Python vs MATLAB)
3. **QC tests**: Compare QC flag arrays (exact match required)
4. **Export tests**: Compare NetCDF structure and content
5. **End-to-end tests**: Raw file → NetCDF comparison

## Roadmap Tracking

### When Implementing New Features
1. Check `python/docs/ROADMAP.md` for the relevant phase
2. Mark items as complete with `[x]` when done
3. Add bookend update entry with date and summary
4. Update `python/docs/PARSER_FORMAT_MATRIX.md` for new parsers

### Current Priorities (as of 2026-06-02)
- **Phase 7**: Dash web UI (mostly complete, need export wiring)
- **Phase 8**: Tests and validation (parsers, preprocessing, QC tests)
- **Phase 10**: MCR-based regression testing infrastructure
- **Phase 11**: SFR integration requirements (input packages, lineage, reprocessing)

## Common Pitfalls

### GSW API Differences
**MATLAB**: `gsw.SP_from_R(R, T, P)` (conductivity ratio)
**Python**: `gsw.SP_from_C(C, T, P)` (conductivity in mS/cm)

Convert MATLAB conductivity ratio to Python conductivity:
```python
C = R * gsw.C3515  # Convert ratio to mS/cm
PSAL = gsw.SP_from_C(C, T, P)
```

### TIME Coordinate Format
All parsers must convert TIME to MATLAB datenum format (days since 0000-01-01) for consistency:
```python
# For IMOS NetCDF (days since 1950-01-01)
time_values = ds["TIME"].values + matlab_datenum_epoch_offset
```

### QC Flag Semantics
**Always upgrade, never downgrade**: If a data point already has `BAD` flag, QC routines should not change it to `GOOD`.

### uv.lock Hygiene
- Always commit `uv.lock` after dependency changes
- Run `uv lock` after editing `pyproject.toml`
- CI enforces lock file is in sync

## Integration Points with MATLAB

### Shared Configuration
Python reads `toolboxProperties.txt` for backward compatibility

### Shared Templates
Python uses NetCDF templates from `NetCDF/template/`

### Shared Conventions
Python uses IMOS conventions from `IMOS/` directory (parameters, QC flags, test definitions)

### Migration Path
The Python port aims for output parity with MATLAB. Users should be able to:
1. Process same raw files with both implementations
2. Get functionally equivalent NetCDF outputs
3. Transition incrementally (mix MATLAB and Python workflows)
