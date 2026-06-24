"""Tests for NetCDF re-import parser."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from imos_toolbox.parsers.netcdf_reimport import NetCDFReimportParser


def test_netcdf_reimport_basic(tmp_path: Path) -> None:
    """Test basic NetCDF re-import with dimensions, variables, and attributes."""
    # Create a minimal synthetic IMOS NetCDF file
    nc_file = tmp_path / "test_data.nc"

    # IMOS stores TIME as days since 1950-01-01
    # For testing, use a few days offset from the IMOS epoch
    time_data = np.array([0.0, 1.0, 2.0, 3.0])  # Days since 1950-01-01

    # Create dataset with IMOS structure
    ds = xr.Dataset(
        {
            "TIME": (["TIME"], time_data, {"long_name": "time", "units": "days since 1950-01-01 00:00:00 UTC"}),
            "TEMP": (["TIME"], np.array([15.2, 15.3, 15.1, 15.4]), {"long_name": "sea_water_temperature", "units": "degrees_Celsius"}),
            "PSAL": (["TIME"], np.array([35.1, 35.2, 35.0, 35.3]), {"long_name": "sea_water_practical_salinity", "units": "1"}),
            "LATITUDE": ([], -33.8, {"long_name": "latitude", "units": "degrees_north"}),
            "LONGITUDE": ([], 151.2, {"long_name": "longitude", "units": "degrees_east"}),
            "NOMINAL_DEPTH": ([], 10.0, {"long_name": "nominal_depth", "units": "m"}),
        },
        attrs={
            "title": "Test IMOS Dataset",
            "institution": "IMOS",
            "featureType": "timeSeries",
            "instrument": "Test Instrument",
            "instrument_serial_no": "12345",
        },
    )

    # Save to NetCDF
    ds.to_netcdf(nc_file)

    # Parse the file
    parser = NetCDFReimportParser()
    result = parser.parse([nc_file], mode="timeSeries")

    # Verify dimensions and coordinates
    assert "TIME" in result.dataset.coords
    assert len(result.dataset["TIME"]) == 4

    # Verify TIME was converted from IMOS epoch to MATLAB datenum
    # MATLAB datenum for 1950-01-01 is 712224 (ordinal 710347 + 366 + 1511)
    # Actually: datetime(1950,1,1).toordinal() = 711858, + 366 = 712224
    expected_matlab_base = datetime(1950, 1, 1).toordinal() + 366
    assert np.allclose(result.dataset["TIME"].values[0], expected_matlab_base, rtol=1e-6)
    assert np.allclose(result.dataset["TIME"].values[1], expected_matlab_base + 1.0, rtol=1e-6)

    # Verify variables
    assert "TEMP" in result.dataset.data_vars
    assert "PSAL" in result.dataset.data_vars
    assert np.allclose(result.dataset["TEMP"].values, [15.2, 15.3, 15.1, 15.4])
    assert np.allclose(result.dataset["PSAL"].values, [35.1, 35.2, 35.0, 35.3])

    # Verify scalar coordinates
    assert "LATITUDE" in result.dataset.data_vars
    assert "LONGITUDE" in result.dataset.data_vars
    assert "NOMINAL_DEPTH" in result.dataset.data_vars
    assert np.isclose(result.dataset["LATITUDE"].values, -33.8)
    assert np.isclose(result.dataset["LONGITUDE"].values, 151.2)
    assert np.isclose(result.dataset["NOMINAL_DEPTH"].values, 10.0)

    # Verify global attributes were preserved
    assert result.dataset.attrs["title"] == "Test IMOS Dataset"
    assert result.dataset.attrs["institution"] == "IMOS"
    assert result.dataset.attrs["featureType"] == "timeSeries"
    assert result.dataset.attrs["instrument"] == "Test Instrument"
    assert result.dataset.attrs["instrument_serial_no"] == "12345"

    # Verify parser metadata was added
    assert result.dataset.attrs["toolbox_input_file"] == str(nc_file)
    assert result.dataset.attrs["parser"] == "netcdfParse"
    assert result.dataset.attrs["source_format"] == "netcdf"
    assert "date_created" in result.dataset.attrs


def test_netcdf_reimport_with_qc_flags(tmp_path: Path) -> None:
    """Test NetCDF re-import preserves QC flags."""
    nc_file = tmp_path / "test_qc.nc"

    time_data = np.array([0.0, 1.0, 2.0])
    temp_data = np.array([15.2, 15.3, 15.1])
    temp_qc = np.array([1, 1, 2], dtype=np.int8)  # IMOS QC flags

    ds = xr.Dataset(
        {
            "TIME": (["TIME"], time_data),
            "TEMP": (["TIME"], temp_data, {"long_name": "temperature"}),
            "TEMP_QC": (["TIME"], temp_qc, {"long_name": "quality flag for temperature"}),
            "LATITUDE": ([], -33.8),
            "LONGITUDE": ([], 151.2),
        },
        attrs={"featureType": "timeSeries"},
    )

    ds.to_netcdf(nc_file)

    parser = NetCDFReimportParser()
    result = parser.parse([nc_file], mode="timeSeries")

    # Verify QC flags were preserved
    assert "TEMP_QC" in result.dataset.data_vars
    assert np.array_equal(result.dataset["TEMP_QC"].values, temp_qc)


def test_netcdf_reimport_profile_mode(tmp_path: Path) -> None:
    """Test NetCDF re-import with profile mode."""
    nc_file = tmp_path / "test_profile.nc"

    depth_data = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
    temp_data = np.array([20.5, 18.2, 16.8, 15.3, 14.1])

    ds = xr.Dataset(
        {
            "DEPTH": (["DEPTH"], depth_data, {"long_name": "depth", "units": "m"}),
            "TEMP": (["DEPTH"], temp_data, {"long_name": "temperature", "units": "degrees_Celsius"}),
            "LATITUDE": ([], -33.8),
            "LONGITUDE": ([], 151.2),
        },
        attrs={"featureType": "profile", "instrument": "CTD"},
    )

    ds.to_netcdf(nc_file)

    parser = NetCDFReimportParser()
    result = parser.parse([nc_file], mode="profile")

    # Verify profile structure
    assert "DEPTH" in result.dataset.coords
    assert len(result.dataset["DEPTH"]) == 5
    assert "TEMP" in result.dataset.data_vars
    assert np.allclose(result.dataset["TEMP"].values, temp_data)
    assert result.dataset.attrs["featureType"] == "profile"


def test_netcdf_reimport_variable_attributes(tmp_path: Path) -> None:
    """Test that variable attributes are preserved during re-import."""
    nc_file = tmp_path / "test_attrs.nc"

    ds = xr.Dataset(
        {
            "TIME": (["TIME"], np.array([0.0, 1.0])),
            "TEMP": (
                ["TIME"],
                np.array([15.2, 15.3]),
                {
                    "long_name": "sea_water_temperature",
                    "standard_name": "sea_water_temperature",
                    "units": "degrees_Celsius",
                    "valid_min": -2.0,
                    "valid_max": 40.0,
                    "ancillary_variables": "TEMP_QC",
                },
            ),
            "LATITUDE": ([], -33.8),
            "LONGITUDE": ([], 151.2),
        },
        attrs={"featureType": "timeSeries"},
    )

    ds.to_netcdf(nc_file)

    parser = NetCDFReimportParser()
    result = parser.parse([nc_file], mode="timeSeries")

    # Verify all variable attributes were preserved
    temp_attrs = result.dataset["TEMP"].attrs
    assert temp_attrs["long_name"] == "sea_water_temperature"
    assert temp_attrs["standard_name"] == "sea_water_temperature"
    assert temp_attrs["units"] == "degrees_Celsius"
    assert temp_attrs["valid_min"] == -2.0
    assert temp_attrs["valid_max"] == 40.0
    assert temp_attrs["ancillary_variables"] == "TEMP_QC"


def test_netcdf_reimport_rejects_multiple_files() -> None:
    """Test that parser rejects multiple input files."""
    parser = NetCDFReimportParser()
    with pytest.raises(ValueError, match="expects exactly one input file"):
        parser.parse(["file1.nc", "file2.nc"], mode="timeSeries")


def test_netcdf_reimport_rejects_wrong_extension(tmp_path: Path) -> None:
    """Test that parser rejects non-NetCDF files."""
    wrong_file = tmp_path / "test.txt"
    wrong_file.write_text("not a netcdf file")

    parser = NetCDFReimportParser()
    with pytest.raises(ValueError, match="expects .nc or .netcdf files"):
        parser.parse([wrong_file], mode="timeSeries")
