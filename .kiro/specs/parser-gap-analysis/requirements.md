# Requirements Document

## Introduction

This document specifies the requirements for a comprehensive parser gap analysis and testing infrastructure for the IMOS Toolbox Python port. The system SHALL analyze all 27 instrument parsers across multiple dimensions: implementation status, format coverage, test coverage, regression testing readiness, and MCR-based validation infrastructure. The feature enables systematic validation of the Python port's parser layer against MATLAB reference outputs and provides actionable gap identification for achieving production-ready parser coverage.

## Glossary

- **Parser**: A Python class inheriting from `BaseParser` that converts raw instrument files into `IMOSDataset` objects
- **PARSER_FORMAT_MATRIX**: The markdown file tracking parser-to-format coverage at `python/docs/PARSER_FORMAT_MATRIX.md`
- **MCR**: MATLAB Component Runtime (v95) used for regression testing without MATLAB licenses
- **IMOSDataset**: xarray-based data model wrapping `xr.Dataset` with IMOS-specific conventions
- **Test_Suite**: The pytest-based test infrastructure under `python/tests/parsers/`
- **Regression_Baseline**: MATLAB-generated reference output for comparison with Python parser results
- **Gap_Report**: Structured analysis document identifying missing tests, untested formats, and validation gaps
- **Format_Coverage**: The percentage of documented instrument file formats with working parser implementations
- **Test_Coverage**: The percentage of parsers with comprehensive pytest test cases
- **Regression_Coverage**: The percentage of parsers with MCR-based regression validation against MATLAB outputs

## Requirements

### Requirement 1: Parser Inventory and Status Analysis

**User Story:** As a Python port maintainer, I want a complete inventory of all 27 parsers with their implementation and testing status, so that I can prioritize gap remediation efforts.

#### Acceptance Criteria

1. THE Analysis_System SHALL extract the complete list of 27 parsers from PARSER_FORMAT_MATRIX with their CLI commands and supported file formats
2. THE Analysis_System SHALL determine implementation status for each parser by checking for existence of parser module in `python/src/imos_toolbox/parsers/`
3. THE Analysis_System SHALL determine test coverage status for each parser by checking for corresponding test module in `python/tests/parsers/`
4. THE Analysis_System SHALL classify each parser into one of five status categories: COMPLETE (implemented with tests), IMPLEMENTED (no tests), PARTIAL (incomplete implementation), STUB (placeholder only), or MISSING (not started)
5. THE Analysis_System SHALL calculate aggregate statistics including total parsers, implementation percentage, test coverage percentage, and gap count
6. THE Analysis_System SHALL generate a structured inventory report in markdown format with parser name, status, CLI command, formats, test status, and notes columns

### Requirement 2: Format Coverage Gap Analysis

**User Story:** As a Python port developer, I want to identify which documented instrument file formats lack parser support, so that I can implement missing format handlers.

#### Acceptance Criteria

1. THE Analysis_System SHALL extract all documented file formats from PARSER_FORMAT_MATRIX for each parser
2. THE Analysis_System SHALL verify format support by checking parser source code for file extension validation logic
3. WHEN a parser claims support for multiple formats (e.g., `.asc`, `.cnv`), THE Analysis_System SHALL verify each format is handled in the parse method
4. THE Analysis_System SHALL identify format gaps where PARSER_FORMAT_MATRIX lists a format but parser code does not handle it
5. THE Analysis_System SHALL identify undocumented formats where parser code handles formats not listed in PARSER_FORMAT_MATRIX
6. THE Analysis_System SHALL generate a format gap report listing parser, expected formats, implemented formats, missing formats, and undocumented formats

### Requirement 3: Test Coverage Gap Analysis

**User Story:** As a QA engineer, I want to identify parsers lacking pytest test coverage, so that I can create comprehensive test cases.

#### Acceptance Criteria

1. THE Analysis_System SHALL identify parsers with no corresponding test file in `python/tests/parsers/`
2. THE Analysis_System SHALL analyze existing test files to count test functions (functions prefixed with `test_`)
3. THE Analysis_System SHALL classify test coverage as NONE (no test file), MINIMAL (1-2 tests), PARTIAL (3-5 tests), GOOD (6-10 tests), or COMPREHENSIVE (11+ tests)
4. THE Analysis_System SHALL identify missing test scenarios including basic parse, multiple file handling, wrong extension rejection, format validation, metadata preservation, TIME coordinate conversion, and QC flag handling
5. THE Analysis_System SHALL calculate test coverage metrics including parsers with tests, average tests per parser, and percentage of parsers with comprehensive coverage
6. THE Analysis_System SHALL generate a test gap report listing parser, test file status, test count, coverage classification, and missing test scenarios

### Requirement 4: MCR Regression Testing Infrastructure Analysis

**User Story:** As a regression testing lead, I want to assess MCR-based regression testing readiness across all parsers, so that I can plan MATLAB-to-Python validation work.

#### Acceptance Criteria

1. THE Analysis_System SHALL identify parsers eligible for MCR regression testing (implemented parsers with MATLAB equivalents)
2. THE Analysis_System SHALL check for existence of MCR baseline generation infrastructure in `python/tests/regression/`
3. THE Analysis_System SHALL verify MCR wrapper module existence and MATLAB Runtime configuration
4. THE Analysis_System SHALL identify parsers with existing regression baselines in `python/tests/regression/baselines/`
5. THE Analysis_System SHALL identify parsers missing regression baselines but eligible for testing
6. THE Analysis_System SHALL calculate regression testing readiness including baseline count, eligible parser count, and coverage percentage
7. THE Analysis_System SHALL generate a regression readiness report listing parser, MATLAB equivalent, baseline status, and regression test status

### Requirement 5: Priority-Based Gap Remediation Plan

**User Story:** As a project manager, I want a prioritized list of parser gaps ordered by impact and effort, so that I can allocate development resources efficiently.

#### Acceptance Criteria

1. THE Analysis_System SHALL assign priority scores to each identified gap using a scoring rubric based on parser usage frequency, data volume, and migration criticality
2. THE Analysis_System SHALL assign effort estimates to each gap using categories: SMALL (1-2 days), MEDIUM (3-5 days), LARGE (1-2 weeks), or XLARGE (2+ weeks)
3. THE Analysis_System SHALL calculate a priority rank for each gap using the formula: rank = (priority_score * 10) / effort_factor
4. THE Analysis_System SHALL classify gaps by type including missing parser implementation, missing format support, missing test coverage, and missing regression baseline
5. THE Analysis_System SHALL group related gaps (e.g., all gaps for a single parser) into remediation tasks
6. THE Analysis_System SHALL generate a prioritized remediation plan in markdown format with task ID, gap type, parser name, priority score, effort estimate, priority rank, and description columns sorted by descending priority rank

### Requirement 6: Automated Gap Analysis Execution

**User Story:** As a CI/CD engineer, I want to run gap analysis automatically on each commit, so that gap reports stay current with code changes.

#### Acceptance Criteria

1. THE Analysis_System SHALL provide a command-line interface with usage: `uv run python -m imos_toolbox.analysis.parser_gaps --output-dir reports/`
2. WHEN invoked with `--output-dir` parameter, THE Analysis_System SHALL write all gap reports to the specified directory
3. THE Analysis_System SHALL generate five output files: parser_inventory.md, format_gaps.md, test_gaps.md, regression_readiness.md, and remediation_plan.md
4. WHEN invoked with `--format json` parameter, THE Analysis_System SHALL output reports in JSON format instead of markdown
5. THE Analysis_System SHALL exit with status code 0 when analysis completes successfully and status code 1 when errors occur
6. THE Analysis_System SHALL complete full analysis of all 27 parsers within 10 seconds on a standard development workstation

### Requirement 7: Parser Implementation Validation

**User Story:** As a Python port developer, I want to verify that implemented parsers follow architectural conventions, so that code quality remains consistent.

#### Acceptance Criteria

1. THE Analysis_System SHALL verify each parser inherits from `BaseParser` class
2. THE Analysis_System SHALL verify each parser implements the `parse(file_paths, mode)` method signature
3. THE Analysis_System SHALL verify each parser returns `IMOSDataset` instances from parse method
4. THE Analysis_System SHALL verify each parser is registered in `python/src/imos_toolbox/parsers/__init__.py` with correct CLI command mapping
5. THE Analysis_System SHALL verify each parser validates file extensions and raises `ValueError` for wrong formats
6. THE Analysis_System SHALL verify each parser converts TIME coordinate to MATLAB datenum format
7. THE Analysis_System SHALL flag architectural violations including missing inheritance, wrong method signatures, missing registration, missing extension validation, and missing TIME conversion

### Requirement 8: Test Case Completeness Validation

**User Story:** As a QA engineer, I want to verify that existing parser tests cover required test scenarios, so that test quality meets standards.

#### Acceptance Criteria

1. THE Analysis_System SHALL define required test scenarios: basic_parse, multiple_files, wrong_extension, format_validation, metadata_preservation, time_conversion, qc_flags, and mode_support
2. THE Analysis_System SHALL analyze each test file to identify which required scenarios have test coverage
3. THE Analysis_System SHALL detect test scenarios by analyzing test function names and pytest fixture usage
4. WHEN a parser supports multiple modes (timeSeries and profile), THE Analysis_System SHALL verify tests exist for both modes
5. WHEN a parser supports multiple formats, THE Analysis_System SHALL verify tests exist for each format
6. THE Analysis_System SHALL calculate completeness percentage as (covered_scenarios / required_scenarios) * 100
7. THE Analysis_System SHALL generate a test completeness report listing parser, test file, covered scenarios, missing scenarios, and completeness percentage

### Requirement 9: MATLAB Parity Gap Analysis

**User Story:** As a migration lead, I want to identify parsers where Python implementation deviates from MATLAB behavior, so that I can ensure output parity.

#### Acceptance Criteria

1. THE Analysis_System SHALL compare parser registry in `python/src/imos_toolbox/parsers/__init__.py` with MATLAB registry in `Parser/instruments.txt`
2. THE Analysis_System SHALL identify Python parsers with no MATLAB equivalent (new implementations)
3. THE Analysis_System SHALL identify MATLAB parsers with no Python equivalent (missing ports)
4. THE Analysis_System SHALL extract parser-to-instrument mappings from MATLAB `instruments.txt` registry
5. THE Analysis_System SHALL verify Python parser names match MATLAB parser function names (case-insensitive, underscore-normalized)
6. THE Analysis_System SHALL generate a parity gap report listing parser, MATLAB status, Python status, and parity notes

### Requirement 10: Regression Test Data Inventory

**User Story:** As a regression testing engineer, I want an inventory of available test data files for each parser, so that I can ensure adequate test data coverage.

#### Acceptance Criteria

1. THE Analysis_System SHALL search for test data files in `python/tests/parsers/data/` and `python/tests/regression/data/` directories
2. THE Analysis_System SHALL associate test data files with parsers based on file extension and directory naming conventions
3. THE Analysis_System SHALL classify test data files as SYNTHETIC (generated in tests), SAMPLE (small real files), or PRODUCTION (full-size deployment files)
4. THE Analysis_System SHALL identify parsers with no test data files available
5. THE Analysis_System SHALL identify parsers with only synthetic test data (no real instrument files)
6. THE Analysis_System SHALL calculate test data coverage as percentage of parsers with real instrument test files
7. THE Analysis_System SHALL generate a test data inventory listing parser, file count, file types, data classification, and notes

### Requirement 11: Gap Analysis Report Aggregation

**User Story:** As a project stakeholder, I want a single executive summary report consolidating all gap analysis dimensions, so that I can understand overall parser readiness.

#### Acceptance Criteria

1. THE Analysis_System SHALL generate an executive summary report named `parser_gap_summary.md`
2. THE Summary_Report SHALL include overall statistics: total parsers, implemented count, tested count, regression-ready count, and overall readiness percentage
3. THE Summary_Report SHALL include a breakdown table showing status distribution across all five status categories
4. THE Summary_Report SHALL include top 10 priority gaps extracted from the remediation plan
5. THE Summary_Report SHALL include risk assessment identifying high-risk gaps (critical parsers with poor coverage)
6. THE Summary_Report SHALL include progress tracking comparing current analysis with previous runs (if historical data exists)
7. THE Summary_Report SHALL include recommendations for immediate actions based on gap severity

### Requirement 12: CI Integration and Failure Thresholds

**User Story:** As a CI/CD engineer, I want gap analysis to fail CI builds when coverage drops below thresholds, so that gaps do not accumulate unnoticed.

#### Acceptance Criteria

1. THE Analysis_System SHALL support configurable thresholds via command-line parameters: `--min-implementation-pct`, `--min-test-pct`, `--min-regression-pct`
2. WHEN implementation percentage falls below `--min-implementation-pct`, THE Analysis_System SHALL exit with status code 2 and print threshold violation message
3. WHEN test coverage percentage falls below `--min-test-pct`, THE Analysis_System SHALL exit with status code 3 and print threshold violation message
4. WHEN regression coverage percentage falls below `--min-regression-pct`, THE Analysis_System SHALL exit with status code 4 and print threshold violation message
5. THE Analysis_System SHALL support `--strict` flag which treats any identified gap as a CI failure
6. THE Analysis_System SHALL support `--ignore-parsers` parameter accepting comma-separated parser names to exclude from threshold checks (for known exceptions)
7. WHEN threshold violations occur, THE Analysis_System SHALL print a summary of violations including actual percentage, threshold percentage, and gap count
