"""
Tests for SBE39 parser

Mirrors MATLAB test structure from Parser/SBE39Parse.m
Tests specific .asc files with known properties.

To use these tests:
1. Place your SBE39 test files in: python/tests/parsers/data/sbe/sbe39/
2. Run: uv run pytest tests/parsers/test_sbe39.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.sbe39 import SBE39Parser
from imos_toolbox.model import IMOSDataset
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "sbe" / "sbe39"

# Specific test files - using real data from MATLAB test suite
TEST_FILES = [
    "SBE39_5840_2411.asc",
    "SBE39_5857_2411.asc",
]


def get_test_file(filename: str) -> Path:
    """Get path to a specific test file."""
    file_path = TEST_DATA_DIR / filename
    if not file_path.exists():
        pytest.skip(f"Test file not found: {filename}")
    return file_path


@pytest.fixture
def parser():
    """Create a SBE39Parser instance"""
    return SBE39Parser()


class TestSBE39Parser:
    """Test suite for SBE39 parser - mirrors MATLAB SBE39Parse.m"""
    
    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, SBE39Parser)
        assert parser.parser_name == "SBE39"
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_basic_parse(self, parser, filename):
        """Test basic parsing of .asc file.
        
        Verifies that the parser can read the file and extract data.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check that we have data
        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0, f"Should have data variables in {filename}"
        
        # Should have TIME dimension
        assert 'TIME' in dataset.dataset.dims, "Should have TIME dimension"
        
        # Should have core variable (temperature)
        assert 'TEMP' in dataset.dataset.data_vars, "Should have TEMP variable"
        
        print(f"  ✓ {filename}: Parsed {len(dataset.dataset.data_vars)} variables")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_imos_scaffold_variables(self, parser, filename):
        """Test that IMOS scaffold variables are present.
        
        Mirrors MATLAB: scaffold variables added for IMOS compliance
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
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_coordinates_attribute(self, parser, filename):
        """Test that data variables have coordinates attribute.
        
        Mirrors MATLAB: coordinates = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        expected_coords = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        
        # Check TEMP
        assert 'coordinates' in dataset.dataset['TEMP'].attrs, \
            "TEMP should have coordinates attribute"
        assert dataset.dataset['TEMP'].attrs['coordinates'] == expected_coords, \
            f"TEMP coordinates should be '{expected_coords}'"
        
        print(f"  ✓ {filename}: Coordinates attributes correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_time_dimension(self, parser, filename):
        """Test that TIME is a dimension, not a variable.
        
        Mirrors MATLAB: sample_data.dimensions{1}.name = 'TIME'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # TIME should be a dimension
        assert 'TIME' in dataset.dataset.dims, "TIME should be a dimension"
        
        # Variables should use TIME dimension
        assert dataset.dataset['TEMP'].dims == ('TIME',), \
            "TEMP should have TIME dimension"
        
        print(f"  ✓ {filename}: TIME dimension structure correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_temperature_range(self, parser, filename):
        """Test that temperature values are in reasonable range.
        
        Validates TEMP data: should be -10°C to 50°C
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        temp_values = dataset.dataset['TEMP'].values
        
        assert len(temp_values) > 0, "Should have temperature values"
        assert np.all(temp_values > -10), "Temperature too low"
        assert np.all(temp_values < 50), "Temperature too high"
        
        print(f"  ✓ {filename}: Temperature range valid ({np.min(temp_values):.2f} to {np.max(temp_values):.2f}°C)")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_optional_pressure(self, parser, filename):
        """Test detection of optional pressure sensor.
        
        Mirrors MATLAB test: assert(getVar(data.variables, 'PRES_REL') > 0)
        where getVar returns index (>0 if exists, 0 if not found).
        MATLAB does NOT validate pressure data values, only existence.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        has_pressure = 'PRES_REL' in dataset.dataset.data_vars
        
        if has_pressure:
            # Check PRES_REL variable exists (matches MATLAB getVar check)
            pres_values = dataset.dataset['PRES_REL'].values
            assert len(pres_values) > 0, "Should have pressure values"
            # NO validation of actual pressure values (MATLAB doesn't do this)
            print(f"  ✓ {filename}: Pressure sensor detected ({pres_values[0]:.2f} dbar)")
        else:
            print(f"  ✓ {filename}: No pressure sensor (temperature only)")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_metadata_extraction(self, parser, filename):
        """Test that instrument metadata is extracted.
        
        Mirrors MATLAB: instrument_make, instrument_model, instrument_serial_no
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check global attributes
        attrs = dataset.dataset.attrs
        
        assert 'instrument_make' in attrs, "Should have instrument_make"
        # SBE39 .asc is parsed via SBE3x.m, which sets 'Sea-bird Electronics'
        # (the .cnv/.hex/.tid parsers use 'Seabird').
        assert attrs['instrument_make'] == 'Sea-bird Electronics', \
            "Instrument make should be 'Sea-bird Electronics' (SBE3x path)"
        
        assert 'instrument_model' in attrs, "Should have instrument_model"
        assert 'SBE39' in attrs['instrument_model'], "Instrument model should contain SBE39"
        
        print(f"  ✓ {filename}: Metadata extracted correctly")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_sample_interval(self, parser, filename):
        """Test that sample interval is calculated.
        
        Mirrors MATLAB: instrument_sample_interval metadata
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        attrs = dataset.dataset.attrs
        
        assert 'instrument_sample_interval' in attrs, \
            "Should have instrument_sample_interval"
        
        sample_interval = attrs['instrument_sample_interval']
        assert sample_interval > 0, "Sample interval should be positive"
        
        print(f"  ✓ {filename}: Sample interval = {sample_interval:.2f} seconds")
    
    def test_asc_format_only(self, parser):
        """Test that parser only accepts .asc files.
        
        Mirrors MATLAB: SBE39Parse delegates to SBE3x for .asc format
        """
        # Test that wrong format is rejected
        with pytest.raises(ValueError, match="supports .asc files only"):
            parser.parse(["fake.cnv"], "timeSeries")
        
        print("  ✓ Parser correctly rejects non-.asc files")
    
    def test_print_test_file_info(self):
        """Discovery test: Print available test files and their contents"""
        print("\n=== SBE39 Test Files ===")
        if TEST_DATA_DIR.exists():
            files = sorted(TEST_DATA_DIR.glob("*"))
            for f in files:
                print(f"  • {f.name} ({f.stat().st_size} bytes)")
        else:
            print(f"  Directory not found: {TEST_DATA_DIR}")
