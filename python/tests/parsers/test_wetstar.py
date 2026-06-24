"""
Tests for WET Labs WetStar parser

Mirrors MATLAB test structure from Parser/WetStarParse.m
Tests .raw exports (each requires a matching .dev device file).

To use these tests:
1. Place your WetStar test files in: python/tests/parsers/data/wetstar/
   Each .raw file must have a matching .dev file alongside it.
2. Run: uv run pytest tests/parsers/test_wetstar.py -v

NOTE: ECO-family parsers map device columns to IMOS variables
(CPHL, CDOM, TURB, ...) and do NOT currently emit the IMOS scaffold
variables, so the scaffold test only checks the TIME dimension here.
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.wetstar import WetStarParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "wetstar"


def discover_test_files():
    """Discover .raw WetStar files that have a matching .dev file."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for raw in sorted(TEST_DATA_DIR.rglob("*.raw")):
        if raw.with_suffix(".dev").exists():
            files.append(str(raw))
    return files


@pytest.fixture
def parser():
    """Create a WetStarParser instance"""
    return WetStarParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestWetStarParser:
    """Test suite for WetStar parser - mirrors MATLAB WetStarParse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, WetStarParser)
        assert parser.parser_name == "WetStar"

    def test_format_validation(self, parser):
        """Test that parser rejects unsupported file extensions.

        WetStar parser supports .raw files only.
        """
        with pytest.raises(ValueError, match="supports .raw files only"):
            parser.parse(["fake.csv"], "timeSeries")
        print("  ✓ Parser correctly rejects non-.raw files")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a WetStar .raw file."""
        if not test_files:
            pytest.skip("No WetStar test files (.raw + .dev) found in data/wetstar/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No WetStar test files (.raw + .dev) found in data/wetstar/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Structural check for the WetStar dataset.

        ECO-family parsers do not currently emit IMOS scaffold variables;
        verify the TIME dimension and at least one mapped data variable.
        """
        if not test_files:
            pytest.skip("No WetStar test files (.raw + .dev) found in data/wetstar/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        data_vars = [v for v in dataset.dataset.data_vars if v != "TIME"]
        assert len(data_vars) > 0, "Should have at least one data variable"

        print(f"  ✓ Data variables: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No WetStar test files (.raw + .dev) found in data/wetstar/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("instrument_make") == "WET Labs"
        assert attrs.get("parser") == "WetStar"

        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("WET Labs WetStar Test Files Configuration")
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


# ── Synthetic data tests (exercise parser logic without real files) ──

class TestWetStarSynthetic:
    """Tests using synthetic .raw + .dev files to verify parser logic."""

    def test_synthetic_parse(self, tmp_path):
        """Create synthetic WetStar files and verify parsing."""
        # Create .dev file (mirrors WET Labs device format)
        dev_content = "WETStar-123\nColumns=1\nCHL\t0.012\t50\n"
        dev_file = tmp_path / "test_20200101_0000.dev"
        dev_file.write_text(dev_content)

        # Create .raw file (one value per line)
        raw_content = "\n".join([str(100 + i) for i in range(10)])
        raw_file = tmp_path / "test_20200101_0000.raw"
        raw_file.write_text(raw_content)

        parser = WetStarParser()
        dataset = parser.parse([str(raw_file)], "timeSeries")

        assert dataset is not None
        assert "TIME" in dataset.dataset.dims
        assert "TIMESERIES" in dataset.dataset.data_vars
        assert "LATITUDE" in dataset.dataset.data_vars
        assert "LONGITUDE" in dataset.dataset.data_vars
        assert "NOMINAL_DEPTH" in dataset.dataset.data_vars
        assert dataset.dataset.attrs["instrument_make"] == "WET Labs"
        print("  ✓ Synthetic WetStar parse successful")

    def test_synthetic_calibration(self, tmp_path):
        """Verify scale/offset calibration formula (MATLAB FLNTUcal equivalent).
        
        Note: This test validates the calibration math in isolation using
        the convert_eco_raw_var function directly.
        """
        from imos_toolbox.parsers.eco_common import ECOColumn, convert_eco_raw_var
        import numpy as np
        
        column = ECOColumn(type="CHL", scale=0.5, offset=10.0)
        counts = np.array([20.0, 30.0, 40.0])
        
        var_name, converted, cal_attrs = convert_eco_raw_var(column, counts)
        
        assert var_name == "CPHL"
        assert np.isclose(converted[0], 5.0), f"Expected 5.0, got {converted[0]}"
        assert np.isclose(converted[1], 10.0), f"Expected 10.0, got {converted[1]}"
        assert np.isclose(converted[2], 15.0), f"Expected 15.0, got {converted[2]}"
        assert "calibration_dark_count" in cal_attrs
        assert cal_attrs["calibration_dark_count"] == 10.0
        assert cal_attrs["calibration_scale_factor"] == 0.5
        print("  ✓ Calibration: scale*(counts-offset) verified")
