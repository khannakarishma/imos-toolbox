"""
Tests for Nortek Continental ADCP parser

Mirrors MATLAB test structure from Parser/continentalParse.m.
Tests binary .cpr format files.

To use these tests:
1. Place your Continental test files in: python/tests/parsers/data/continental/v000/trip_*/
2. Each trip folder should contain at least one .cpr binary file.
3. Run: uv run pytest tests/parsers/test_continental.py -v

There is currently no sample data for this parser; tests skip gracefully
when no files are present.
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.continental import ContinentalParser
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "Nortek" / "continental"


def discover_test_files():
    """Discover all Continental test files (.cpr)."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    # Accept both v000/trip_* layout and flat layout.
    for pattern in ("v000/trip_*/*.cpr", "**/*.cpr"):
        for f in TEST_DATA_DIR.glob(pattern):
            if str(f) not in files:
                files.append(str(f))
    return files


@pytest.fixture
def parser():
    """Create a ContinentalParser instance."""
    return ContinentalParser()


@pytest.fixture
def test_files():
    """Discover all available test files."""
    return discover_test_files()


class TestContinentalParser:
    """Test suite for Continental parser - mirrors MATLAB continentalParse.m."""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated."""
        assert parser is not None
        assert isinstance(parser, ContinentalParser)
        assert parser.parser_name == "Continental"

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a .cpr binary file."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims

    def test_dimensions(self, parser, test_files):
        """Test that required dimensions are present."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        has_dist = (
            "DIST_ALONG_BEAMS" in dataset.dataset.dims
            or "HEIGHT_ABOVE_SENSOR" in dataset.dataset.dims
        )
        assert has_dist, "Should have DIST_ALONG_BEAMS or HEIGHT_ABOVE_SENSOR dimension"

    def test_velocity_variables(self, parser, test_files):
        """Test that velocity variables are present (ENU or Beam)."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        enu_vars = ["UCUR_MAG", "VCUR_MAG", "WCUR"]
        beam_vars = ["VEL1", "VEL2", "VEL3"]
        found_enu = [v for v in enu_vars if v in dataset.dataset.data_vars]
        found_beam = [v for v in beam_vars if v in dataset.dataset.data_vars]

        assert len(found_enu) >= 2 or len(found_beam) >= 2, (
            f"Should have velocity variables. Found ENU: {found_enu}, Beam: {found_beam}"
        )

    def test_backscatter_variables(self, parser, test_files):
        """Test that backscatter intensity variables are present (3-beam)."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        backscatter_vars = ["ABSIC1", "ABSIC2", "ABSIC3"]
        found_vars = [v for v in backscatter_vars if v in dataset.dataset.data_vars]
        assert len(found_vars) >= 2, f"Should have backscatter variables, found: {found_vars}"

    def test_sensor_variables(self, parser, test_files):
        """Test that sensor data variables are present."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        expected = ["TEMP", "PRES_REL", "HEADING_MAG", "PITCH", "ROLL"]
        found = [v for v in expected if v in dataset.dataset.data_vars]
        assert len(found) >= 3, f"Should have sensor variables, found: {found}"

    def test_imos_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present and scalar."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        for name in ("TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"):
            assert name in dataset.dataset.data_vars, f"Should have {name}"
            assert dataset.dataset[name].dims == (), f"{name} should be scalar"

    def test_metadata_extraction(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        for key in ("instrument_make", "instrument_model", "instrument_serial_no", "featureType"):
            assert key in attrs, f"Should have {key}"

        assert attrs["instrument_make"] == "Nortek"
        assert attrs["instrument_model"] == "Continental"
        # Continental includes timeSeries data, so featureType is empty.
        assert attrs["featureType"] == ""

    def test_coordinates_attribute(self, parser, test_files):
        """Test that 2D data variables carry a coordinates attribute."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")

        for var_name, var in dataset.dataset.data_vars.items():
            if len(var.dims) == 2:
                assert "coordinates" in var.attrs, (
                    f"{var_name} should have coordinates attribute"
                )
                break

    def test_temperature_range(self, parser, test_files):
        """Temperature values should be reasonable for an ocean deployment."""
        if not test_files:
            pytest.skip("No test files found")

        dataset = parser.parse([test_files[0]], "timeSeries")
        if "TEMP" not in dataset.dataset.data_vars:
            pytest.skip("No TEMP variable in dataset")

        temp_values = dataset.dataset["TEMP"].values
        valid = temp_values[~np.isnan(temp_values)]
        if len(valid) > 0:
            assert np.all(valid > -5), "Temperature too low"
            assert np.all(valid < 40), "Temperature too high"


def test_print_test_file_info():
    """Print information about available test files."""
    print(f"\n{'=' * 70}")
    print("Nortek Continental ADCP Test Files Configuration")
    print(f"{'=' * 70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n\u26a0 WARNING: No test files found!")
        print("Expected files in:")
        print(f"  - {TEST_DATA_DIR}/v000/trip_*/*.cpr")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            size_kb = fp.stat().st_size / 1024
            print(f"  {fp.parent.name}/{fp.name} ({size_kb:.1f} KB)")
    print(f"{'=' * 70}\n")
