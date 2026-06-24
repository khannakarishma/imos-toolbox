"""SBE26 parser implementation (.tid support with IMOS compliance)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser


class SBE26Parser(BaseParser):
    """Parser for Sea-Bird SBE26 Temperature and Pressure Logger .tid files.
    
    Mirrors MATLAB SBE26Parse.m implementation.
    
    File format: measurement_no mm/dd/yyyy HH:MM:SS pressure_psia temperature_c
    """

    parser_name = "SBE26"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("SBE26 parser currently expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".tid":
            raise ValueError("SBE26 parser currently supports .tid files only")

        return _parse_tid_to_dataset(
            source_file=source_file,
            mode=mode,
            parser_name=self.parser_name,
        )


def _parse_tid_to_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
) -> IMOSDataset:
    """Parse SBE26 .tid file to IMOSDataset.
    
    Mirrors MATLAB SBE26Parse.m structure:
    1. Parse file format with textscan equivalent
    2. Convert units (psia → dbar)
    3. Adjust TIME to center of measurement (+2 minutes)
    4. Build dataset with IMOS scaffold variables
    5. Add applied offset and coordinates
    
    Args:
        source_file: Path to .tid file
        mode: 'timeSeries' or 'profile'
        parser_name: Parser name
        
    Returns:
        IMOSDataset with IMOS-compliant structure
    """
    # Parse data file
    time_values, pressures_dbar, temps = _read_tid_data(source_file)
    
    if not temps:
        raise ValueError(f"No valid SBE26 samples found in {source_file}")
    
    # Calculate sample interval
    time_array = np.asarray(time_values, dtype=float)
    time_diff_seconds = np.diff(time_array * 24 * 3600)
    sample_interval = float(np.median(time_diff_seconds))
    
    # Build IMOS-compliant dataset
    dataset = _build_sbe26_dataset(
        time_values=time_array,
        pressures=np.asarray(pressures_dbar, dtype=float),
        temperatures=np.asarray(temps, dtype=float),
        source_file=source_file,
        mode=mode,
        parser_name=parser_name,
        sample_interval=sample_interval,
    )
    
    return dataset


def _read_tid_data(source_file: Path) -> tuple[list[float], list[float], list[float]]:
    """Read and parse .tid file data.
    
    Mirrors MATLAB textscan with format: '%*d %f %f %f %f %f %f %f %f'
    Delimiter: space, '/', ':'
    
    Expected columns:
    - measurement_no (ignored)
    - month / day / year (mm/dd/yyyy)
    - hour : minute : second (HH:MM:SS)
    - pressure (psia)
    - temperature (°C)
    
    Args:
        source_file: Path to .tid file
        
    Returns:
        Tuple of (time_values, pressures_dbar, temperatures)
    """
    time_values: list[float] = []
    pressures_dbar: list[float] = []
    temps: list[float] = []
    
    content = source_file.read_text(encoding="utf-8", errors="ignore")
    
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        
        # Split by delimiters: space, '/', ':'
        # Replace delimiters with spaces for uniform splitting
        line_normalized = line.replace('/', ' ').replace(':', ' ')
        tokens = line_normalized.split()
        
        # Expected: meas_no M D Y H MN S pressure temp
        if len(tokens) < 9:
            continue
        
        try:
            # Parse date/time components (indices 1-6)
            month = int(tokens[1])
            day = int(tokens[2])
            year = int(tokens[3])
            hour = int(tokens[4])
            minute = int(tokens[5])
            # MATLAB reads seconds with %f - support fractional seconds
            second_f = float(tokens[6])
            
            # Parse data (indices 7-8)
            pressure_psia = float(tokens[7])
            temp_c = float(tokens[8])
            
            # Create datetime (split fractional seconds into microseconds)
            whole_seconds = int(second_f)
            microseconds = int(round((second_f - whole_seconds) * 1_000_000))
            dt = datetime(year, month, day, hour, minute, whole_seconds, microseconds)
            
        except (ValueError, IndexError):
            continue
        
        # MATLAB: time = datenum(Y, M, D, H, MN+2, S)
        # Adds 2 minutes to represent center of 4-minute measurement window
        dt_center = dt + timedelta(minutes=2)
        
        # Convert to MATLAB datenum
        time_values.append(_datetime_to_matlab_datenum(dt_center))
        
        # Convert pressure: psia → dbar (1 psi = 0.6894757 dbar)
        pressures_dbar.append(pressure_psia * 0.6894757)
        
        # Temperature already in °C
        temps.append(temp_c)
    
    return time_values, pressures_dbar, temps


def _build_sbe26_dataset(
    time_values: np.ndarray,
    pressures: np.ndarray,
    temperatures: np.ndarray,
    source_file: Path,
    mode: str,
    parser_name: str,
    sample_interval: float,
) -> IMOSDataset:
    """Build IMOS-compliant dataset for SBE26.
    
    Mirrors MATLAB structure:
    - TIME dimension
    - Scaffold variables: TIMESERIES, LATITUDE, LONGITUDE, NOMINAL_DEPTH
    - Data variables: PRES_REL, TEMP
    - Applied offset on PRES_REL
    - Coordinates attribute
    
    Args:
        time_values: TIME array (MATLAB datenum)
        pressures: PRES_REL array (dbar)
        temperatures: TEMP array (°C)
        source_file: Source file path
        mode: 'timeSeries' or 'profile'
        parser_name: Parser name
        sample_interval: Median time difference in seconds
        
    Returns:
        IMOSDataset with complete IMOS structure
    """
    dataset = IMOSDataset.empty()
    
    # TIME dimension (not a variable in timeSeries mode)
    time_dim = "TIME"
    dataset.add_dimension(time_dim, time_values)
    
    # Scaffold variables (scalars, no dimensions)
    dataset.add_variable(
        name='TIMESERIES',
        data=np.int32(1),
        dims=[],
        attrs={'long_name': 'timeSeries index', 'cf_role': 'timeseries_id'},
    )
    
    dataset.add_variable(
        name='LATITUDE',
        data=np.float64(np.nan),
        dims=[],
        attrs={'long_name': 'latitude', 'units': 'degrees_north'},
    )
    
    dataset.add_variable(
        name='LONGITUDE',
        data=np.float64(np.nan),
        dims=[],
        attrs={'long_name': 'longitude', 'units': 'degrees_east'},
    )
    
    dataset.add_variable(
        name='NOMINAL_DEPTH',
        data=np.float32(np.nan),
        dims=[],
        attrs={'long_name': 'nominal depth', 'units': 'meters', 'positive': 'down'},
    )
    
    # Coordinates string for data variables
    coordinates = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
    
    # PRES_REL variable
    # Applied offset: -14.7*0.689476 = -10.1325 dbar (atmospheric pressure)
    dataset.add_variable(
        name='PRES_REL',
        data=pressures,
        dims=[time_dim],
        attrs={
            'coordinates': coordinates,
            'applied_offset': np.float32(-14.7 * 0.689476),
            'comment': 'Relative pressure with atmospheric offset of -10.13 dbar applied by SeaBird software.',
        },
    )
    
    # TEMP variable
    dataset.add_variable(
        name='TEMP',
        data=temperatures,
        dims=[time_dim],
        attrs={
            'coordinates': coordinates,
        },
    )
    
    # Global attributes
    dataset.set_attrs(
        {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "Seabird",
            "instrument_model": "SBE26",
            "instrument_firmware": "",
            "instrument_serial_no": "",
            "instrument_sample_interval": sample_interval,
            "parser": parser_name,
            "source_format": "tid",
        }
    )
    
    # Add TIME dimension comment
    dataset.dataset['TIME'].attrs['comment'] = (
        'Time stamp corresponds to the centre of the measurement which lasts 4 minutes.'
    )
    
    return dataset


def _datetime_to_matlab_datenum(value: datetime) -> float:
    """Convert Python datetime to MATLAB datenum.
    
    MATLAB datenum is days since 0000-01-01 (proleptic Gregorian calendar).
    Python's ordinal is days since 0001-01-01, so we add 366 days.
    
    Args:
        value: Python datetime
        
    Returns:
        MATLAB datenum (float)
    """
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac

