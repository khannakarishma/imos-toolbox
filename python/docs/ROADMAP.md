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
- [x] Add preprocessing base class (`PPRoutine`, `PPResult`) and chain runner (`run_pp_chain`)
- [x] Implement pressureRelPP (PRES_REL = PRES + offset, default -10.1325 dbar)
- [x] Implement depthPP using gsw (DEPTH = -gsw.z_from_p(PRES_REL, lat); fallback 1 dbar ≈ 1 m)
- [x] Implement salinityPP using gsw (PSAL from CNDC, TEMP, PRES_REL via gsw.SP_from_C)
- [x] Implement oxygenPP using gsw (OXSOL_SURFACE, DOX1, DOX2, DOXS conversions)
- [x] Implement velocityMagDirPP (CSPD/CDIR from UCUR/VCUR)
- [x] Implement timeOffsetPP (UTC timezone correction; parses numeric, UTC±HH[:MM])
- [x] Implement timeDriftPP (linear time-drift correction between start/end offsets)
- [x] Implement variableOffsetPP (data = offset + scale * data for named variables)
- [x] Wire `preprocess` CLI command for default timeSeries/profile chains
- [x] Add 31 unit tests (all passing), ruff clean, mypy clean
- [ ] Implement magneticDeclinationPP using pyIGRF or equivalent
- [ ] Implement adcpBinMappingPP
- [ ] Implement adcpNortekVelocityBeam2EnuPP
- [ ] Implement adcpNortekVelocityEnu2BeamPP
- [ ] Implement adcpWorkhorseVelocityBeam2EnuPP
- [ ] Implement transformPP
- [ ] Implement absiDecibelBasicPP
- [ ] Implement aquatrackaPP
- [ ] Implement rinkoDoPP
- [ ] Implement CTDDepthBinPP
- [ ] Implement timeMetaOffsetPP
- [ ] Implement timeStartPP
- [ ] Implement soakStatusPP

## Phase 4 - Automatic QC
- [x] Add QC base classes and chain runner
- [x] Implement imosImpossibleDateQC
- [x] Implement imosImpossibleLocationSetQC
- [x] Implement imosInOutWaterQC
- [x] Implement imosGlobalRangeQC
- [x] Implement imosRegionalRangeQC
- [x] Implement imosImpossibleDepthQC
- [x] Implement imosSalinityFromPTQC
- [x] Implement imosRateOfChangeQC
- [x] Implement imosTimeSeriesSpikeQC
- [x] Implement imosVerticalSpikeQC
- [x] Implement imosDensityInversionSetQC
- [x] Implement imosStationarityQC
- [x] Implement CTDSurfaceSoakQC
- [x] Implement imosSurfaceDetectionByDepthSetQC
- [ ] Implement imosSideLobeVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosTiltVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosHorizontalVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosVerticalVelocityQC (ADCP-specific, lower priority)
- [ ] Implement imosCorrMagVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosEchoIntensitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosEchoIntensityVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosEchoRangeSetQC (ADCP-specific, lower priority)
- [ ] Implement imosErrorVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosPercentGoodVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement imosTier2ProfileVelocitySetQC (ADCP-specific, lower priority)
- [ ] Implement teledyneSetQC (ADCP-specific, lower priority)
- [ ] Implement imosHistoricalManualSetQC (lower priority)
- [x] Port spike classifiers (Hampel implemented)

## Phase 5 - NetCDF/Parquet/Zarr export
- [ ] Implement NetCDF template parser
- [ ] Implement makeNetCDFCompliant logic
- [ ] Implement NetCDF export writer
- [ ] Implement Parquet export writer (parallel to NetCDF outputs)
- [ ] Capture and persist dataset/variable metadata in Parquet outputs
- [ ] Implement Zarr export target for suitable multidimensional data types
- [ ] Capture and persist dataset/variable metadata in Zarr outputs
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
- [ ] Add CLI options to select export targets (NetCDF, Parquet, Zarr where applicable)
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
- [x] Wire Start page to real parser/file loading into in-memory dataset state
- [x] Drive preview table/plots from parsed dataset state
- [x] Drive spike/manual QC actions from in-memory dataset state

## Phase 8 - Tests and validation
- [ ] Add pytest scaffolding and fixtures
- [x] Add parser format test matrix
- [x] Add UI state mutation tests (spike/manual/manual file parsing)
- [x] Add UI callback wiring regression check for manual flag path
- [ ] Port representative parser tests
- [ ] Port preprocessing/QC tests
- [ ] Add NetCDF regression tests
- [ ] Add Parquet regression tests (including metadata round-trip checks)
- [ ] Add Zarr regression tests for eligible multidimensional datasets (including metadata round-trip checks)
- [ ] Add CI checks (lint, typecheck, tests)

## Phase 9 - Documentation and release
- [ ] Add user and developer docs
- [ ] Add migration notes from MATLAB
- [ ] Publish first alpha release to PyPI

## Bookend update (2026-02-17)
- [x] Verified local Dash UI launch with optional `ui` dependencies.
- [x] Verified parser-to-UI dataset load path with a Vemco sample file.
- [x] Verified end-to-end manual flagging state mutation path (`dataset-store` updates QC flags).
- [x] Added regression coverage for manual-flag callback wiring.
- [ ] Next session: wire export flow from in-memory QC state to file outputs.

## Bookend update (2026-03-02)
- [x] Phase 4 foundation: added QC base classes (`QCFlags`, `QCResult`, `QCVariableRoutine`, `QCSetRoutine`) and chain runner with flag-upgrade-only semantics.
- [x] Implemented 6 automatic QC routines: `ImpossibleDateQC`, `ImpossibleLocationSetQC`, `InOutWaterQC`, `GlobalRangeQC`, `RegionalRangeQC`, `ImpossibleDepthQC`.
- [x] Created 41 unit tests with synthetic oceanographic data (SBE37 at NRSMAI, GBR temperature logger at GBRHIS).
- [x] All quality gates passing: 85 tests green, ruff clean, mypy clean.
- [ ] Next session: continue Phase 4 with `imosSalinityFromPTQC`, `imosRateOfChangeQC`, spike classifiers, and remaining QC routines.

## Bookend update (2026-03-03) – session 2
- [x] Ported the preprocessing pipeline (Phase 3) — default timeSeries and profile chains fully operational.
- [x] Added `preprocessing/` subpackage with `PPRoutine` / `PPResult` base class and `run_pp_chain` runner (mirrors autoqc architecture).
- [x] Implemented 9 preprocessing routines: `pressureRelPP`, `depthPP`, `salinityPP`, `oxygenPP`, `velocityMagDirPP`, `timeOffsetPP`, `timeDriftPP`, `variableOffsetPP`.
- [x] Fixed gsw Python API difference (`gsw.SP_from_C` instead of MATLAB `gsw.SP_from_R(R, T, P)`).
- [x] Wired `preprocess` CLI command for default timeSeries/profile chains on existing NetCDF files.
- [x] Added 31 unit tests (all passing, including full chain integration test).
- [x] All quality gates passing: 146 tests green, ruff clean, mypy clean.
- [x] **Phase 3 core preprocessing complete** (ADCP-specific and minor routines remain).
- [ ] Next session: begin Phase 5 NetCDF export, or port remaining preprocessing ADCP/transform routines.
- [x] Implemented `RateOfChangeQC` routine to detect rapid changes in parameter values using gradient thresholds.
- [x] Implemented `TimeSeriesSpikeQC` routine using Hampel filter for spike detection in time series.
- [x] Implemented `VerticalSpikeQC` routine using ARGO spike test for vertical profiles.
- [x] Implemented `DensityInversionSetQC` routine to detect density inversions in profiles.
- [x] Implemented `StationarityQC` routine to flag flatline (constant value) regions.
- [x] Implemented `CTDSurfaceSoakQC` routine to flag CTD data during surface soak period.
- [x] Implemented `SurfaceDetectionByDepthSetQC` routine to flag ADCP bins above water surface.
- [x] Created spike classifier infrastructure with Hampel filter implementation.
- [x] Added 30 comprehensive unit tests across all new routines.
- [x] All quality gates passing: 115 tests green, ruff clean, mypy clean.
- [x] **14 out of 28 QC routines complete (50% of Phase 4)**
- [x] Core QC routines complete; remaining are ADCP-specific (lower priority for general use)
- [ ] Next: Move to Phase 5 (NetCDF/Parquet/Zarr export) or implement ADCP routines as needed
