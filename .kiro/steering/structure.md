# Project Structure

## Root Directory Layout

```
imos-toolbox/
├── AutomaticQC/          # MATLAB QC test implementations
├── DDB/                  # Deployment database access layer (JDBC/ODBC)
├── FlowManager/          # MATLAB workflow orchestration
│   ├── autoIMOSToolbox.m      # Batch mode entry point
│   ├── flowManager.m          # Interactive workflow manager
│   ├── importManager.m        # Parser selection and data import
│   ├── preprocessManager.m    # Preprocessing chain execution
│   ├── autoQCManager.m        # QC chain execution
│   └── exportManager.m        # NetCDF export
├── Geomag/               # Magnetic declination binaries (linux/windows/macosx)
├── Graph/                # Visualization and plotting
├── GUI/                  # MATLAB GUI components
├── IMOS/                 # IMOS-specific conventions and parameters
├── Java/                 # Java libraries (JDBC drivers, DDB access)
├── NetCDF/               # NetCDF export logic and templates
│   └── template/         # Attribute templates for NetCDF output
├── Parser/               # Instrument file parsers
│   └── instruments.txt   # Parser-to-instrument mapping registry
├── Preprocessing/        # Data transformation routines
├── Seawater/             # Oceanographic calculations (legacy)
├── Util/                 # Utility functions and helpers
├── test/                 # MATLAB unit tests
├── python/               # Python port (active development)
│   ├── docs/             # Python-specific documentation
│   ├── src/              # Python source code
│   ├── tests/            # Python test suite
│   ├── pyproject.toml    # Python package configuration
│   └── uv.lock           # Dependency lockfile
├── imosToolbox.m         # Main MATLAB entry point
├── build.py              # Build script for stand-alone application
└── toolboxProperties.txt # Global configuration
```

## Python Port Structure

```
python/
├── src/imos_toolbox/
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration loader
│   ├── conventions/            # IMOS conventions (parameters, QC flags, etc.)
│   ├── model/                  # Data model (IMOSDataset wrapper)
│   ├── parsers/                # Instrument file parsers
│   │   ├── base.py             # Parser base class
│   │   ├── __init__.py         # Parser registry
│   │   ├── sbe19.py            # SeaBird SBE19 parser
│   │   ├── sbe26.py            # SeaBird SBE26 parser
│   │   ├── sbe37.py            # SeaBird SBE37 parser
│   │   ├── wqm.py              # WET Labs WQM parser
│   │   ├── vemco.py            # Vemco Minilog parser
│   │   └── ...                 # Additional parsers
│   ├── preprocessing/          # Data transformation routines
│   │   ├── base.py             # Preprocessing base class
│   │   ├── runner.py           # Chain execution
│   │   └── routines/           # Individual preprocessing routines
│   ├── autoqc/                 # Automatic QC checks
│   │   ├── base.py             # QC base class
│   │   ├── runner.py           # Chain execution
│   │   └── routines/           # Individual QC routines
│   ├── export/                 # Output generation
│   │   ├── netcdf.py           # NetCDF export
│   │   └── templates.py        # Template parsing
│   ├── ddb/                    # Deployment database access
│   │   └── schema.py           # SQLAlchemy schema models
│   └── ui/                     # Dash web interface
│       ├── app.py              # Dash application
│       ├── pages/              # UI page components
│       └── callbacks/          # Interactive callbacks
├── tests/                      # Python test suite
│   ├── parsers/                # Parser tests
│   ├── preprocessing/          # Preprocessing tests
│   ├── autoqc/                 # QC tests
│   └── ui/                     # UI tests
├── docs/                       # Documentation
│   ├── ROADMAP.md              # Migration progress tracking
│   ├── SCHEMA.md               # DDB schema documentation
│   ├── PARSER_FORMAT_MATRIX.md # Parser coverage matrix
│   └── MCR_REGRESSION_PLAN.md  # Regression testing strategy
├── pyproject.toml              # Package configuration
├── uv.lock                     # Dependency lockfile
├── .python-version             # Python version (3.14)
├── Makefile                    # Development shortcuts
└── README.md                   # Python port README
```

## Key MATLAB Modules

### FlowManager (Workflow Orchestration)
- **Entry points**: `imosToolbox.m` (interactive), `autoIMOSToolbox.m` (batch)
- **Managers**: Import → Preprocess → Display → AutoQC → Export
- Each manager handles one stage of the pipeline

### Parser (Data Import)
- **Registry**: `Parser/instruments.txt` maps make/model to parser function
- **Format**: Each parser returns a MATLAB struct with standardized schema
- **Naming**: Parser files follow pattern `<instrument>Parse.m`

### AutomaticQC (Quality Control)
- **Registry**: `AutomaticQC/` contains individual QC test functions
- **Naming**: IMOS QC tests prefixed with `imos` (e.g., `imosGlobalRangeQC.m`)
- **Chains**: Configurable via `toolboxProperties.txt`

### Preprocessing (Data Transformation)
- **Location**: `Preprocessing/` contains individual routines
- **Naming**: Suffixed with `PP` (e.g., `depthPP.m`, `salinityPP.m`)
- **Common routines**: Pressure → depth, conductivity → salinity, oxygen conversions

### NetCDF Export
- **Templates**: `NetCDF/template/` contains attribute templates
- **Token syntax**: `[mat ...]` for MATLAB eval, `[ddb ...]` for database lookup
- **Compliance**: `makeNetCDFCompliant.m` applies IMOS conventions

## Python Module Organization

### Parsers (`parsers/`)
- Each parser inherits from `BaseParser`
- Registry in `__init__.py` maps CLI commands to parser classes
- Consistent API: `parse(file_paths, mode) → IMOSDataset`

### Preprocessing (`preprocessing/`)
- Base class: `PPRoutine` with `process(dataset) → PPResult`
- Chain runner: `run_pp_chain(dataset, routines, mode)`
- Default chains defined for timeSeries and profile modes

### Auto QC (`autoqc/`)
- Base classes: `QCVariableRoutine` (per-variable), `QCSetRoutine` (multi-variable)
- Chain runner: `run_qc_chain(dataset, routines, mode)`
- Flag upgrade-only semantics (never downgrade QC flags)

### Export (`export/`)
- Template parser: `parse_template(template_file, dataset, mode)`
- NetCDF writer: `export_netcdf(dataset, output_path, mode)`
- Compression enabled by default (zlib level 4)

### UI (`ui/`)
- Dash multi-page application
- Pages: Start, Preview, Metadata, QC Summary, Spike Selection, Manual Flagging, Export
- Callbacks handle user interactions and state mutations

## Configuration Files

### Global Configuration
- `toolboxProperties.txt`: MATLAB and shared settings
- Format: `key = value` with `%` comments
- Sections: DDB connection, execution mode, QC chains, preprocessing chains, UI formatting

### Python Configuration
- `python/pyproject.toml`: Package metadata, dependencies, tool configs
- `python/.python-version`: Python version pin (3.14)
- `python/uv.lock`: Exact dependency versions (committed)

## Data Flow

### MATLAB Pipeline
```
Raw File → Parser → MATLAB Struct → Preprocessing → Auto QC → Manual QC (GUI) → NetCDF Export
```

### Python Pipeline
```
Raw File → Parser → IMOSDataset (xarray) → Preprocessing → Auto QC → UI Interaction → NetCDF Export
```

## Naming Conventions

### MATLAB
- **Functions**: camelCase (e.g., `imosToolbox`, `parseNetCDF`)
- **Classes**: PascalCase with `@` directories (e.g., `@DepthProfile/`)
- **Packages**: `+PackageName/` directories
- **Variables**: camelCase

### Python
- **Modules**: snake_case (e.g., `sbe37.py`, `global_range_qc.py`)
- **Classes**: PascalCase (e.g., `SBE37Parser`, `GlobalRangeQC`)
- **Functions**: snake_case (e.g., `parse_template`, `run_qc_chain`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `QC_FLAGS`, `DEFAULT_CHAIN`)

## Testing Structure

### MATLAB Tests
- Location: `test/` directory
- Organization: Mirrors source structure (`test/Parser/`, `test/Util/`)
- Naming: Prefix `test` (e.g., `testSBE19Parse.m`)
- Runner: `runalltests.bat` (Windows) or `runalltests.sh` (Linux)

### Python Tests
- Location: `python/tests/` directory
- Framework: pytest
- Organization: Mirrors source structure (`tests/parsers/`, `tests/autoqc/`)
- Naming: Prefix `test_` (e.g., `test_sbe37.py`)
- Runner: `uv run pytest -v`

## Documentation

### MATLAB Documentation
- Wiki: https://github.com/aodn/imos-toolbox/wiki
- Inline: Function headers with MATLAB doc format

### Python Documentation
- Location: `python/docs/`
- Key files:
  - `ROADMAP.md`: Migration progress and feature checklist
  - `SCHEMA.md`: Deployment database schema
  - `PARSER_FORMAT_MATRIX.md`: Parser implementation status
  - `MCR_REGRESSION_PLAN.md`: Regression testing strategy
- Inline: Python docstrings (Google style preferred)
