# IMOS Toolbox Python Port - Roadmap

This roadmap tracks the Python port plan and progress. Check items off as work is completed.

## Phase 1 - Scaffold and core model
- [x] Create package layout under python/
- [x] Add core IMOSDataset wrapper and helpers
- [x] Add config loader for toolboxProperties.txt
- [x] Add conventions loaders (parameters, QC flags, QC tests, file versions, sites, naming)
- [x] Add CLI entrypoint skeleton

## Phase 2 - Parser framework and mapping
- [ ] Add parser base class and registry
- [ ] Load parser mapping from Parser/instruments.txt
- [ ] Implement SBE19 parser
- [ ] Implement SBE26 parser
- [ ] Implement SBE37 parser
- [ ] Implement SBE37SM parser
- [ ] Implement SBE39 parser
- [ ] Implement SBE56 parser
- [ ] Implement SBE3x shared logic
- [ ] Implement Workhorse ADCP parser
- [ ] Implement AWAC parser
- [ ] Implement Continental parser
- [ ] Implement Aquadopp Profiler parser
- [ ] Implement Aquadopp Velocity parser
- [ ] Implement Signature/AD2CP parser
- [ ] Implement OceanContour parser
- [ ] Implement WQM parser
- [ ] Implement WetStar parser
- [ ] Implement ECOBB9 parser
- [ ] Implement ECO Triplet parser
- [ ] Implement XR parser
- [ ] Implement DR1050 parser
- [ ] Implement Vemco parser
- [ ] Implement NIWA parser
- [ ] Implement NXIC binary parser
- [ ] Implement Starmon Mini parser
- [ ] Implement Starmon DST parser
- [ ] Implement Aquatec parser
- [ ] Implement Sensus Ultra parser
- [ ] Implement Echoview parser
- [ ] Implement Infinity SD Logger parser
- [ ] Implement RCM parser
- [ ] Implement YSI 6-Series parser
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
- [ ] Scaffold Dash app and layout
- [ ] Implement data exploration views
- [ ] Implement QC interaction views (spike selection, manual flagging)
- [ ] Implement export flow
- [ ] Add plot exports
- [ ] Implement start page (mode, data dir, field trip, DDB)
- [ ] Implement dataset preview page
- [ ] Implement metadata editor page
- [ ] Implement QC summary/stats page
- [ ] Implement spike selection page
- [ ] Implement manual flagging page
- [ ] Implement graph export page
- [ ] Implement log/diagnostics page

## Phase 8 - Tests and validation
- [ ] Add pytest scaffolding and fixtures
- [ ] Port representative parser tests
- [ ] Port preprocessing/QC tests
- [ ] Add NetCDF regression tests
- [ ] Add CI checks (lint, typecheck, tests)

## Phase 9 - Documentation and release
- [ ] Add user and developer docs
- [ ] Add migration notes from MATLAB
- [ ] Publish first alpha release to PyPI
