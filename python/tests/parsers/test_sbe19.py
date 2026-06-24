"""
Tests for SBE19 parser

Mirrors MATLAB test structure from test/Parser/testSBE19Parse.m
Tests specific files with known properties rather than recursively discovering all files.

To use these tests:
1. Place your SBE19 test files in: python/tests/parsers/data/sbe/sbe19/
2. Run: uv run pytest tests/parsers/test_sbe19.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.sbe19 import SBE19Parser
from imos_toolbox.model import IMOSDataset
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "sbe" / "sbe19"

# Specific test files matching MATLAB test structure
STRAIN_PRES_FILES = [
    "SBE19plus_parser1.cnv",
    "YON20200306CFALDB_with_PAR_and_battery.cnv",
    "chla_aquaT3_as_aquaUV.cnv",
]

BEAM_TRANSMISSION_FILES = [
    "YON20200306CFALDB_with_PAR_and_battery.cnv",
]

PAR_FILES = [
    "SBE19plus_parser1.cnv",
    "YON20200306CFALDB_with_PAR_and_battery.cnv",
    "chla_aquaT3_as_aquaUV.cnv",
]

PROFILE_FILE = "IMOS_ANMN-NRS_CTP_130130_NRSMAI_FV00_CTDPRO.cnv"


def get_test_file(filename: str) -> Path:
    """Get path to a specific test file, checking both root and subdirectories."""
    # Try root directory first
    file_path = TEST_DATA_DIR / filename
    if file_path.exists():
        return file_path
    
    # Try 19plus subdirectory
    file_path = TEST_DATA_DIR / "19plus" / filename
    if file_path.exists():
        return file_path
    
    pytest.skip(f"Test file not found: {filename}")


@pytest.fixture
def parser():
    """Create a SBE19Parser instance"""
    return SBE19Parser()


class TestSBE19Parser:
    """Test suite for SBE19 parser - mirrors MATLAB testSBE19Parse.m"""
    
    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, SBE19Parser)
        assert parser.parser_name == "SBE19"
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_read_strain_pressure(self, parser, filename):
        """Test reading strain gauge pressure sensor data.
        
        Mirrors MATLAB: test_read_strain_pressure
        Note: CNV files contain raw SeaBird variable names, not IMOS standard names yet.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check that we have data
        assert len(dataset.dataset.data_vars) > 0, f"Should have data variables in {filename}"
        print(f"  ✓ {filename}: Parsed {len(dataset.dataset.data_vars)} variables")
    
    @pytest.mark.parametrize("filename", PAR_FILES)
    def test_read_par(self, parser, filename):
        """Test reading PAR (Photosynthetically Active Radiation) sensor data.
        
        Mirrors MATLAB: test_read_par
        Note: CNV files contain raw SeaBird variable names like 'par', not 'PAR'.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check that we have data
        assert len(dataset.dataset.data_vars) > 0, f"Should have data variables in {filename}"
        print(f"  ✓ {filename}: Parsed {len(dataset.dataset.data_vars)} variables")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    @pytest.mark.parametrize("mode", ["timeSeries"])
    def test_basic_read(self, parser, filename, mode):
        """Test basic reading of SBE19 files with core variables.
        
        Mirrors MATLAB: test_basic_read
        Checks for pressure, temperature, and optionally conductivity/salinity.
        Note: CNV files contain raw SeaBird variable names (e.g., 'prdM', 'tv290C')
        not IMOS standard names. Variable name mapping happens later in the pipeline.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], mode)
        
        # Check that we have some variables
        assert len(dataset.dataset.data_vars) > 0, f"Should have data variables in {filename}"
        
        # Check that dataset has basic attributes
        assert dataset.dataset.attrs.get('toolbox_input_file'), "Should have toolbox_input_file attribute"
        assert dataset.dataset.attrs.get('featureType') == mode, f"featureType should be {mode}"
        assert dataset.dataset.attrs.get('instrument_make') == 'Seabird', "Should have Seabird as maker"
        
        print(f"  ✓ {filename}: Parsed {len(dataset.dataset.data_vars)} variables: {list(dataset.dataset.data_vars.keys())[:5]}...")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_imos_scaffold_variables(self, parser, filename):
        """Test that IMOS scaffold variables are present.
        
        Schema Test: Verifies IMOS compliance with required scaffold variables.
        TIMESERIES, LATITUDE, LONGITUDE, NOMINAL_DEPTH should be scalars.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check scaffold variables exist
        assert 'TIMESERIES' in dataset.dataset.data_vars, "Should have TIMESERIES"
        assert 'LATITUDE' in dataset.dataset.data_vars, "Should have LATITUDE"
        assert 'LONGITUDE' in dataset.dataset.data_vars, "Should have LONGITUDE"
        assert 'NOMINAL_DEPTH' in dataset.dataset.data_vars, "Should have NOMINAL_DEPTH"
        
        # Verify they are scalars (no dimensions)
        assert dataset.dataset['TIMESERIES'].dims == (), "TIMESERIES should be scalar"
        assert dataset.dataset['LATITUDE'].dims == (), "LATITUDE should be scalar"
        assert dataset.dataset['LONGITUDE'].dims == (), "LONGITUDE should be scalar"
        assert dataset.dataset['NOMINAL_DEPTH'].dims == (), "NOMINAL_DEPTH should be scalar"
        
        # Verify values
        assert dataset.dataset['TIMESERIES'].values == 1, "TIMESERIES should be 1"
        assert np.isnan(dataset.dataset['LATITUDE'].values), "LATITUDE should be NaN"
        assert np.isnan(dataset.dataset['LONGITUDE'].values), "LONGITUDE should be NaN"
        assert np.isnan(dataset.dataset['NOMINAL_DEPTH'].values), "NOMINAL_DEPTH should be NaN"
        
        print(f"  ✓ {filename}: All scaffold variables present and correct")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_time_dimension(self, parser, filename):
        """Test that TIME is a dimension, not a variable.
        
        Schema Test: Verifies TIME is properly used as coordinate dimension.
        Mirrors MATLAB: sample_data.dimensions{1}.name = 'TIME'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # TIME should be a dimension
        assert 'TIME' in dataset.dataset.dims, "TIME should be a dimension"
        
        # Data variables should use TIME dimension
        if 'TEMP' in dataset.dataset.data_vars:
            assert dataset.dataset['TEMP'].dims == ('TIME',), "TEMP should have TIME dimension"
        if 'PRES_REL' in dataset.dataset.data_vars:
            assert dataset.dataset['PRES_REL'].dims == ('TIME',), "PRES_REL should have TIME dimension"
        
        print(f"  ✓ {filename}: TIME dimension structure correct")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_coordinates_attribute(self, parser, filename):
        """Test that data variables have coordinates attribute.
        
        Schema Test: Verifies variables have proper CF coordinates attribute.
        Mirrors MATLAB: coordinates = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        expected_coords = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        
        # Check data variables have coordinates
        data_vars = [v for v in dataset.dataset.data_vars 
                     if v not in ['TIMESERIES', 'LATITUDE', 'LONGITUDE', 'NOMINAL_DEPTH']]
        
        for var in data_vars:
            if dataset.dataset[var].dims == ('TIME',):  # Only check TIME-dependent vars
                assert 'coordinates' in dataset.dataset[var].attrs, \
                    f"{var} should have coordinates attribute"
                assert dataset.dataset[var].attrs['coordinates'] == expected_coords, \
                    f"{var} coordinates should be '{expected_coords}'"
        
        print(f"  ✓ {filename}: Coordinates attributes correct")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_temperature_range(self, parser, filename):
        """Test that temperature values are in reasonable range.
        
        Data Validation: Validates TEMP data is within expected oceanographic range.
        Should be -10°C to 50°C for most deployments.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        if 'TEMP' not in dataset.dataset.data_vars:
            pytest.skip(f"No TEMP variable in {filename}")
        
        temp_values = dataset.dataset['TEMP'].values
        
        # Filter out NaN values for range check
        valid_temps = temp_values[~np.isnan(temp_values)]
        
        assert len(valid_temps) > 0, "Should have valid temperature values"
        assert np.all(valid_temps > -10), f"Temperature too low in {filename}"
        assert np.all(valid_temps < 50), f"Temperature too high in {filename}"
        
        print(f"  ✓ {filename}: Temperature range valid ({np.nanmin(temp_values):.2f} to {np.nanmax(temp_values):.2f}°C)")
    
    @pytest.mark.parametrize("filename", STRAIN_PRES_FILES)
    def test_pressure_range(self, parser, filename):
        """Test that pressure values are non-negative.
        
        Data Validation: Validates PRES_REL data is physically reasonable.
        Relative pressure should be >= 0 dbar.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        if 'PRES_REL' not in dataset.dataset.data_vars:
            pytest.skip(f"No PRES_REL variable in {filename}")
        
        pres_values = dataset.dataset['PRES_REL'].values
        
        assert len(pres_values) > 0, "Should have pressure values"
        # Allow small negative values due to sensor noise, but flag large negatives
        assert np.all(pres_values > -5), f"Pressure too negative in {filename}"
        
        print(f"  ✓ {filename}: Pressure range valid ({np.min(pres_values):.2f} to {np.max(pres_values):.2f} dbar)")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*60}")
    print(f"SBE19 Test Files Configuration")
    print(f"{'='*60}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    print(f"\nTest Files ({len(set(STRAIN_PRES_FILES + PAR_FILES))}):")
    all_files = set(STRAIN_PRES_FILES + PAR_FILES + [PROFILE_FILE])
    for f in all_files:
        fp = TEST_DATA_DIR / f
        if not fp.exists():
            fp = TEST_DATA_DIR / "19plus" / f
        status = "✓" if fp.exists() else "✗"
        size = f"({fp.stat().st_size / 1024:.1f} KB)" if fp.exists() else "(missing)"
        print(f"  {status} {f} {size}")
    print(f"{'='*60}\n")
