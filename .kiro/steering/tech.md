# Technology Stack

## MATLAB Implementation

### Requirements
- MATLAB R2018b or newer for library usage
- MATLAB Compiler Toolbox for building stand-alone applications
- MCR v95 (MATLAB Component Runtime) for stand-alone deployment

### Build System
- **Build script**: `build.py` (Python-based)
- **Supported platforms**: Windows (win64), Linux (glnxa64), macOS (maci64)
- **Java components**: Apache Ant for building Java libraries in `Java/` directory

### Key MATLAB Toolboxes
- Signal Processing Toolbox
- Statistics Toolbox
- Image Processing Toolbox

### Java Dependencies
- JDBC drivers for deployment database connectivity
- UCanAccess for MS-Access database support
- All `.jar` files in `Java/` are dynamically loaded at runtime

### Common Commands (MATLAB)

```bash
# Build stand-alone application (Windows)
python build.py --arch=win64 --matlab_path="C:\Program Files\MATLAB\R2018b"

# Build stand-alone application (Linux)
python build.py --arch=glnxa64 --matlab_path="/opt/MATLAB/R2018b"

# Build with Java dependencies
python build.py --arch=win64 --build-java-deps

# Check repository status only
python build.py --check-repo-only

# Dry run (no actual build)
python build.py --dry-run

# Run tests (Windows)
runalltests.bat

# Run tests (Linux)
./runalltests.sh

# Launch toolbox GUI
matlab -r "imosToolbox"

# Launch in batch mode
matlab -r "imosToolbox('auto', 'inFile', 'input.txt')"

# Check version
matlab -r "imosToolbox('version')"
```

## Python Implementation

### Environment
- **Python version**: 3.14 (pinned via `.python-version`)
- **Package manager**: `uv` (single source of truth for dependencies)
- **Virtual environment**: `.venv` (project-local)

### Core Dependencies
- **xarray**: Multi-dimensional labeled arrays (core data model)
- **netCDF4**: NetCDF file I/O
- **gsw**: TEOS-10 Gibbs SeaWater Oceanographic Toolbox
- **pandas**: Time series and tabular data handling
- **numpy**: Numerical computations
- **dash**: Web UI framework
- **plotly**: Interactive plotting
- **SQLAlchemy**: Database schema and ORM
- **jsonschema**: Schema validation

### Development Tools
- **pytest**: Testing framework
- **ruff**: Fast Python linter and formatter
- **mypy**: Static type checking
- **docopt**: CLI argument parsing

### Common Commands (Python)

```bash
# Environment setup
cd python
python -m pip install uv
uv python install 3.14
uv venv --python 3.14 .venv
uv sync --extra dev

# Development workflow
uv run imos-toolbox info              # Show version and config
uv run pytest -v                      # Run tests
uv run ruff check src tests           # Lint code
uv run mypy src                       # Type check

# Launch Dash UI
uv sync --extra ui --extra dev
uv run imos-toolbox ui --host 127.0.0.1 --port 8050

# CLI processing examples
uv run imos-toolbox parse-sbe37 --file data.asc --mode timeSeries
uv run imos-toolbox preprocess --file parsed.nc --mode timeSeries
uv run imos-toolbox export --file processed.nc --output-dir output --mode timeSeries

# End-to-end pipeline
uv run imos-toolbox process --file raw_data.asc --output-dir output --mode timeSeries --parser sbe37

# Makefile shortcuts
make test                             # Run pytest
make lint                             # Run ruff
make typecheck                        # Run mypy
make lock-check                       # Verify uv.lock is synced
```

### Dependency Management

```bash
# Add new dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update lockfile after pyproject.toml changes
uv lock

# Sync environment with lockfile
uv sync --extra dev

# Clean environment and rebuild
rm -rf .venv
uv venv --python 3.14 .venv
uv sync --extra dev
```

## Configuration

### MATLAB Configuration
- **Main config**: `toolboxProperties.txt`
- **Format**: Key-value pairs with `%` comments
- **Deployment database**: ODBC DSN, JDBC connection, or CSV directory
- **Mode**: `timeSeries` or `profile`
- **QC chains**: Configurable auto QC and preprocessing routines
- **Template directory**: NetCDF attribute templates

### Python Configuration
- **Package config**: `python/pyproject.toml`
- **Lockfile**: `python/uv.lock` (committed)
- **Python version**: `python/.python-version`
- Inherits conventions from MATLAB `toolboxProperties.txt` when available

## Database Access

- **Deployment Database (DDB)**: MS-Access (via UCanAccess JDBC) or CSV flat files
- **Schema**: See `python/docs/SCHEMA.md` for inferred schema and ERD
- **Tables**: FieldTrip, DeploymentData, CTDData, Sites, Instruments, Sensors, InstrumentSensorConfig, Personnel
- **Python schema module**: `imos_toolbox.ddb.schema` (SQLAlchemy models + JSON Schema)

## External Tools

### MATLAB
- **Geomag**: Magnetic declination calculations (compiled binaries in `Geomag/linux`, `Geomag/windows`, `Geomag/macosx`)

### Python
- Uses Python equivalents (gsw for seawater calculations, pyIGRF planned for magnetic declination)
