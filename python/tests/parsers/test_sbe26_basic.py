"""Basic tests for SBE26 parser to verify IMOS compliance."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pytest

from imos_toolbox.parsers.sbe26 import SBE26Parser


@pytest.fixture
def sample_tid_file():
    """Create a minimal .tid file for testing."""
    content = """1 01/15/2020 10:00:00 14.7 20.5
2 01/15/2020 10:15:00 15.2 20.6
3 01/15/2020 10:30:00 15.8 20.7
4 01/15/2020 10:45:00 16.3 20.8
5 01/15/2020 11:00:00 16.9 20.9
"""
    with NamedTemporaryFile(mode='w', suffix='.tid', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    temp_path.unlink()


def test_sbe26_parser_exists():
    """Test that SBE26Parser exists and is properly configured."""
    parser = SBE26Parser()
    assert parser.parser_name == "SBE26"


def test_sbe26_basic_parse(sample_tid_file):
    """Test basic parsing of .tid file."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # Check dataset structure
    assert dataset is not None
    assert 'TIME' in dataset.dataset.dims
    assert 'PRES_REL' in dataset.dataset.data_vars
    assert 'TEMP' in dataset.dataset.data_vars
    
    # Check data values
    assert len(dataset.dataset['PRES_REL']) == 5
    assert len(dataset.dataset['TEMP']) == 5


def test_sbe26_imos_scaffold_variables(sample_tid_file):
    """Test that IMOS scaffold variables are present."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # Check scaffold variables (scalars)
    assert 'TIMESERIES' in dataset.dataset.data_vars
    assert 'LATITUDE' in dataset.dataset.data_vars
    assert 'LONGITUDE' in dataset.dataset.data_vars
    assert 'NOMINAL_DEPTH' in dataset.dataset.data_vars
    
    # Verify they are scalars (no dimensions)
    assert dataset.dataset['TIMESERIES'].dims == ()
    assert dataset.dataset['LATITUDE'].dims == ()
    assert dataset.dataset['LONGITUDE'].dims == ()
    assert dataset.dataset['NOMINAL_DEPTH'].dims == ()
    
    # Verify values
    assert dataset.dataset['TIMESERIES'].values == 1
    assert np.isnan(dataset.dataset['LATITUDE'].values)
    assert np.isnan(dataset.dataset['LONGITUDE'].values)
    assert np.isnan(dataset.dataset['NOMINAL_DEPTH'].values)


def test_sbe26_applied_offset(sample_tid_file):
    """Test that PRES_REL has applied_offset attribute."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    pres_rel = dataset.dataset['PRES_REL']
    assert 'applied_offset' in pres_rel.attrs
    
    # Check value: -14.7 * 0.689476 ≈ -10.1325
    expected_offset = -14.7 * 0.689476
    assert abs(pres_rel.attrs['applied_offset'] - expected_offset) < 0.001


def test_sbe26_coordinates_attribute(sample_tid_file):
    """Test that data variables have coordinates attribute."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # Both PRES_REL and TEMP should have coordinates
    assert 'coordinates' in dataset.dataset['PRES_REL'].attrs
    assert 'coordinates' in dataset.dataset['TEMP'].attrs
    
    expected_coords = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
    assert dataset.dataset['PRES_REL'].attrs['coordinates'] == expected_coords
    assert dataset.dataset['TEMP'].attrs['coordinates'] == expected_coords


def test_sbe26_time_dimension(sample_tid_file):
    """Test that TIME is a dimension, not a variable."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # TIME should be a dimension
    assert 'TIME' in dataset.dataset.dims
    
    # Variables should use TIME dimension
    assert dataset.dataset['PRES_REL'].dims == ('TIME',)
    assert dataset.dataset['TEMP'].dims == ('TIME',)


def test_sbe26_time_centering(sample_tid_file):
    """Test that TIME is adjusted by +2 minutes (center of 4-min measurement)."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # Check TIME dimension comment
    assert 'comment' in dataset.dataset['TIME'].attrs
    assert '4 minutes' in dataset.dataset['TIME'].attrs['comment'].lower()


def test_sbe26_pressure_conversion(sample_tid_file):
    """Test that pressure is converted from psia to dbar."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    # First data point: 14.7 psia * 0.6894757 ≈ 10.13 dbar
    pressure_values = dataset.dataset['PRES_REL'].values
    expected_first = 14.7 * 0.6894757
    assert abs(pressure_values[0] - expected_first) < 0.01


def test_sbe26_global_attributes(sample_tid_file):
    """Test that global attributes are set correctly."""
    parser = SBE26Parser()
    dataset = parser.parse([str(sample_tid_file)], "timeSeries")
    
    attrs = dataset.dataset.attrs
    
    # Check required attributes
    assert attrs['instrument_make'] == 'Seabird'
    assert attrs['instrument_model'] == 'SBE26'
    assert attrs['featureType'] == 'timeSeries'
    assert 'instrument_sample_interval' in attrs
    
    # Sample interval should be ~900 seconds (15 minutes)
    assert 800 < attrs['instrument_sample_interval'] < 1000
