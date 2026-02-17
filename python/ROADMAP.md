# IMOS Toolbox Python Port - Roadmap

This roadmap tracks the Python port plan and progress. Check items off as work is completed.

## Phase 1 - Scaffold and core model
- [x] Install uv for environment and dependency management
- [x] Bootstrap local Python environment with uv (.venv + sync)
- [x] Pin project interpreter via .python-version (3.14)
- [x] Validate CLI boot using uv run
- [x] Create package layout under python/
- [x] Add core IMOSDataset wrapper and helpers
- [x] Add config loader for toolboxProperties.txt
- [x] Add conventions loaders (parameters, QC flags, QC tests, file versions, sites, naming)
- [x] Add CLI entrypoint skeleton

## Python Development Setup (Detailed)

This section is the canonical setup guide for contributors working on the Python port.

### Environment management standard
- [x] Use `uv` as the single environment and dependency manager for this project
- [x] Keep a project-local virtual environment at `python/.venv`
- [x] Pin interpreter target in `python/.python-version` to `3.14`

### Bootstrap steps (fresh clone)
- [x] Install uv (`python -m pip install uv` or official installer)
- [x] Install Python 3.14 runtime via uv (`uv python install 3.14`)
- [x] Create `.venv` with pinned runtime (`uv venv --python 3.14 .venv`)
- [x] Sync dependencies (`uv sync --extra dev`)

### Day-to-day development workflow
- [x] Add README section with UV-first commands and examples
- [x] Standardize all project commands through `uv run` (tests, lint, type checks, CLI)
- [x] Add contributor command reference for:
	- [x] `uv run imos-toolbox info`
	- [x] `uv run pytest -v`
	- [x] `uv run ruff check src tests`
	- [x] `uv run mypy src`

### Verification and diagnostics
- [x] Verify interpreter (`uv run python --version` reports 3.14.x)
- [x] Verify package entrypoint (`uv run imos-toolbox info`)
- [x] Add a `make`/task alias or script targets (optional) for common uv commands
- [x] Document common setup failures and fixes (broken local Python, stale `.venv`, lock mismatch)

### Dependency/lock hygiene
- [x] Keep `uv.lock` committed and updated when dependencies change
- [ ] Define policy for dependency updates (e.g., scheduled bump window)
- [x] Add CI check to ensure lockfile is in sync with `pyproject.toml`

## Phase 2 - Parser framework and mapping
- [x] Add parser base class and registry
- [x] Load parser mapping from Parser/instruments.txt
- [x] Implement SBE19 parser
- [x] Implement SBE26 parser
- [x] Implement SBE37 parser
- [x] Implement SBE37SM parser
- [x] Implement SBE39 parser
- [x] Implement SBE56 parser
- [x] Implement SBE3x shared logic
- [ ] Implement Workhorse ADCP parser
- [ ] Implement AWAC parser
- [ ] Implement Continental parser
- [ ] Implement Aquadopp Profiler parser
- [ ] Implement Aquadopp Velocity parser
- [ ] Implement Signature/AD2CP parser
- [ ] Implement OceanContour parser
- [x] Implement WQM parser
- [x] Implement WetStar parser
- [x] Implement ECOBB9 parser
- [x] Implement ECO Triplet parser
- [x] Implement XR parser
- [x] Implement DR1050 parser
- [x] Implement Vemco parser
- [x] Implement NIWA parser
- [ ] Implement NXIC binary parser
- [x] Implement Starmon Mini parser
- [x] Implement Starmon DST parser
- [x] Implement Aquatec parser
- [x] Implement Sensus Ultra parser
- [ ] Implement Echoview parser
- [ ] Implement Infinity SD Logger parser
- [x] Implement RCM parser
- [x] Implement YSI 6-Series parser
- [ ] Implement NetCDF re-import parser
- [ ] Port GenericParser framework

## Phase 3 - Preprocessing
- [ ] Add preprocessing base class and chain runner
- [ ] Implement depthPP using gsw
- [ ] Implement salinityPP using gsw
- [ ] Implement oxygenPP using gsw
- [ ] Implement pressureRelPP
- [ ] Implement magneticDeclinationPP using pyIGRF
- [ ] Implement velocityMagDirPP
- [ ] Implement adcpBinMappingPP
- [ ] Implement adcpNortekVelocityBeam2EnuPP
- [ ] Implement adcpNortekVelocityEnu2BeamPP
- [ ] Implement adcpWorkhorseVelocityBeam2EnuPP
- [ ] Implement transformPP
- [ ] Implement absiDecibelBasicPP
- [ ] Implement aquatrackaPP
- [ ] Implement rinkoDoPP
- [ ] Implement CTDDepthBinPP
- [ ] Implement timeDriftPP
- [ ] Implement timeOffsetPP
- [ ] Implement timeMetaOffsetPP
- [ ] Implement timeStartPP
- [ ] Implement soakStatusPP
- [ ] Implement variableOffsetPP

## Phase 4 - Automatic QC
- [ ] Add QC base classes and chain runner
- [ ] Implement imosImpossibleDateQC
- [ ] Implement imosImpossibleLocationSetQC
- [ ] Implement imosInOutWaterQC
- [ ] Implement imosGlobalRangeQC
- [ ] Implement imosRegionalRangeQC
- [ ] Implement imosImpossibleDepthQC
- [ ] Implement imosSalinityFromPTQC
- [ ] Implement imosRateOfChangeQC
- [ ] Implement imosTimeSeriesSpikeQC
- [ ] Implement imosVerticalSpikeQC
- [ ] Implement imosDensityInversionSetQC
- [ ] Implement imosStationarityQC
- [ ] Implement CTDSurfaceSoakQC
- [ ] Implement imosSideLobeVelocitySetQC
- [ ] Implement imosTiltVelocitySetQC
- [ ] Implement imosHorizontalVelocitySetQC
- [ ] Implement imosVerticalVelocityQC
- [ ] Implement imosCorrMagVelocitySetQC
- [ ] Implement imosEchoIntensitySetQC
- [ ] Implement imosEchoIntensityVelocitySetQC
- [ ] Implement imosEchoRangeSetQC
- [ ] Implement imosErrorVelocitySetQC
- [ ] Implement imosPercentGoodVelocitySetQC
- [ ] Implement imosSurfaceDetectionByDepthSetQC
- [ ] Implement imosTier2ProfileVelocitySetQC
- [ ] Implement teledyneSetQC
- [ ] Implement imosHistoricalManualSetQC
- [ ] Port spike classifiers (SavGol, Hampel, RunningStats, OTSU, others)

## Phase 5 - NetCDF export
- [ ] Implement NetCDF template parser
- [ ] Implement makeNetCDFCompliant logic
- [ ] Implement NetCDF export writer
- [ ] Implement finaliseData equivalent
- [ ] Port global_attributes_timeSeries template
- [ ] Port global_attributes_profile template
- [ ] Port time_attributes template
- [ ] Port depth_attributes template
- [ ] Port latitude_attributes template
- [ ] Port longitude_attributes template
- [ ] Port nominal_depth_attributes template
- [ ] Port instrument_index_attributes template
- [ ] Port instrument_attributes template
- [ ] Port variable_attributes template
- [ ] Port qc_attributes template
- [ ] Port traj_quality_control_attributes template
- [ ] Port dist_along_beams_attributes template
- [ ] Port dist_along_beams_qc_attributes template
- [ ] Port height_above_sensor_attributes template
- [ ] Port spct_attributes template
- [ ] Port sswv_attributes template
- [ ] Port sswv_qc_attributes template
- [ ] Port triaxys_attributes template
- [ ] Port triaxys_qc_attributes template
- [ ] Port platform-specific templates (Aurora, Rehua, Saxon_onward, default)

## Phase 6 - Pipeline and CLI
- [ ] Implement import manager
- [ ] Implement preprocess manager wiring
- [ ] Implement auto QC manager wiring
- [ ] Implement export manager wiring
- [ ] Add CLI commands for batch processing
- [ ] Wire parser selection by instrument metadata
- [ ] Wire DDB metadata lookup and caching
- [ ] Implement batch entrypoint equivalent to autoIMOSToolbox
- [ ] Implement interactive workflow hooks for UI callbacks
- [ ] Add CLI options for QC/PP chain overrides
- [ ] Add CLI options for DDB connection settings
- [ ] Add CLI options for template and export settings
- [ ] Add CLI options for log/diagnostic output

## Phase 7 - Dash web UI
- [x] Scaffold Dash app and layout
- [x] Implement data exploration views
- [x] Implement QC interaction views (spike selection, manual flagging)
- [x] Implement export flow
- [x] Add plot exports
- [x] Implement start page (mode, data dir, field trip, DDB)
- [x] Implement dataset preview page
- [x] Implement metadata editor page
- [x] Implement QC summary/stats page
- [x] Implement spike selection page
- [x] Implement manual flagging page
- [x] Implement graph export page
- [x] Implement log/diagnostics page

## Phase 8 - Tests and validation
- [ ] Add pytest scaffolding and fixtures
- [x] Add parser format test matrix
- [ ] Port representative parser tests
- [ ] Port preprocessing/QC tests
- [ ] Add NetCDF regression tests
- [ ] Add CI checks (lint, typecheck, tests)

## Phase 9 - Documentation and release
- [ ] Add user and developer docs
- [ ] Add migration notes from MATLAB
- [ ] Publish first alpha release to PyPI
