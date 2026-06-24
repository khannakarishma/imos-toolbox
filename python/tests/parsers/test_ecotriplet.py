"""
Tests for WET Labs ECO Triplet parser

Mirrors MATLAB test structure from Parser/ECOTripletParse.m
Tests .raw exports (each requires a matching .dev device file).

To use these tests:
1. Place your ECO Triplet test files in: python/tests/parsers/data/ecotriplet/
   Each .raw file must have a matching .dev file alongside it.
2. Run: uv run pytest tests/parsers/test_ecotriplet.py -v

NOTE: ECO-family parsers map device columns to IMOS variables and do
NOT currently emit the IMOS scaffold variables, so the scaffold test
only checks the TIME dimension here.
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.ecotriplet import ECOTripletParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "ECOTriplet"


def discover_test_files():
    """Discover .raw ECO Triplet files that have a matching .dev file."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for raw in sorted(TEST_DATA_DIR.rglob("*.raw")):
        if raw.with_suffix(".dev").exists():
            files.append(str(raw))
    return files


@pytest.fixture
def parser():
    """Create an ECOTripletParser instance"""
    return ECOTripletParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestECOTripletParser:
    """Test suite for ECO Triplet parser - mirrors MATLAB ECOTripletParse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, ECOTripletParser)
        assert parser.parser_name == "ECOTriplet"

    def test_format_validation(self, parser):
        """Test that parser rejects unsupported file extensions.

        ECOTriplet parser supports .raw files only.
        """
        with pytest.raises(ValueError, match="supports .raw files only"):
            parser.parse(["fake.csv"], "timeSeries")
        print("  ✓ Parser correctly rejects non-.raw files")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of an ECO Triplet .raw file."""
        if not test_files:
            pytest.skip("No ECO Triplet test files (.raw + .dev) found in data/ecotriplet/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No ECO Triplet test files (.raw + .dev) found in data/ecotriplet/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Structural check for the ECO Triplet dataset.

        ECO-family parsers do not currently emit IMOS scaffold variables;
        verify the TIME dimension and at least one mapped data variable.
        """
        if not test_files:
            pytest.skip("No ECO Triplet test files (.raw + .dev) found in data/ecotriplet/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        data_vars = [v for v in dataset.dataset.data_vars if v != "TIME"]
        assert len(data_vars) > 0, "Should have at least one data variable"

        print(f"  ✓ Data variables: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No ECO Triplet test files (.raw + .dev) found in data/ecotriplet/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("instrument_make") == "WET Labs"
        assert attrs.get("parser") == "ECOTriplet"

        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("WET Labs ECO Triplet Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.raw (each with a matching *.dev)")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")
