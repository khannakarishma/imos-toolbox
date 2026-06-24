"""SBE37 parser implementation (.asc, .cnv, and .DAT hex support)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.parsers.seabird_common import parse_cnv_to_dataset, parse_sbe3x_asc_to_dataset


class SBE37Parser(BaseParser):
    """Parser for Sea-Bird SBE37 output files.
    
    Mirrors MATLAB SBE37Parse.m implementation.
    
    Supports:
    - .asc: ASCII format (TEMP, CNDC, PRES_REL, PSAL, date, time)
    - .cnv: SeaBird CNV format
    - .DAT: SBE37-IM hex format from OOI (USA)
    """

    parser_name = "SBE37"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("SBE37 parser currently expects exactly one input file")

        source_file = file_list[0]
        suffix = source_file.suffix.lower()

        # Check if it's a .DAT file with hex format
        if suffix == ".dat":
            # Read first line to check if it's OOI hex format
            first_line = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
            if first_line == '//Status Information':
                return _parse_sbe37_dat_hex(source_file, mode, self.parser_name)
        
        if suffix == ".cnv":
            return parse_cnv_to_dataset(
                source_file=source_file,
                mode=mode,
                parser_name=self.parser_name,
                instrument_model="SBE37",
            )
        if suffix == ".asc":
            return parse_sbe3x_asc_to_dataset(
                source_file=source_file,
                mode=mode,
                parser_name=self.parser_name,
                instrument_model="SBE37",
            )

        raise ValueError("SBE37 parser currently supports .asc, .cnv, and .DAT files")


def _parse_sbe37_dat_hex(
    source_file: Path,
    mode: str,
    parser_name: str,
) -> IMOSDataset:
    """Parse SBE37-IM .DAT hex format file.
    
    Mirrors MATLAB SBE37Parse.m implementation for .DAT files.
    Corresponds to the section starting with:
        if strcmpi(ext, '.DAT') && strcmp(line, '//Status Information')
    
    Args:
        source_file: Path to .DAT file
        mode: 'timeSeries' or 'profile'
        parser_name: Parser name
        
    Returns:
        IMOSDataset with IMOS-compliant structure
    """
    # Read file and separate sections
    content = source_file.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    
    inst_header_lines: list[str] = []
    data_lines: list[str] = []
    
    in_header = False
    in_data = False
    
    for line in lines:
        line_stripped = line.strip()
        
        if not line_stripped:
            continue
        
        if line_stripped == '//Status Information':
            in_header = True
            in_data = False
            continue
        elif line_stripped == '//Begin Data':
            in_header = False
            in_data = True
            continue
        elif line_stripped == '//End Data':
            break
        
        if in_header:
            inst_header_lines.append(line_stripped)
        elif in_data:
            data_lines.append(line_stripped)
    
    # Parse instrument header (mirrors parseInstrumentHeader)
    inst_header = _parse_instrument_header(inst_header_lines)
    
    # Parse hex data (mirrors readSBE37hex)
    data = _read_sbe37_hex(data_lines, inst_header)
    
    # Calculate sample interval
    if 'sampleInterval' in inst_header:
        sample_interval = inst_header['sampleInterval']
    else:
        time_diff = np.diff(data['TIME'] * 24 * 3600)
        sample_interval = float(np.median(time_diff))
    
    # Build dataset (mirrors structure creation in MATLAB)
    dataset = IMOSDataset.empty()
    
    # TIME dimension
    time_dim = "TIME"
    dataset.add_dimension(time_dim, data['TIME'])
    
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
    
    # Add data variables (skip TIME)
    # Mirrors: for k = 1:length(vars)
    for var_name in data.keys():
        if var_name == 'TIME':
            continue
        
        attrs = {'coordinates': coordinates}
        
        # Add applied offset for pressure
        # Mirrors: if strncmp('PRES_REL', vars{k}, 8)
        if var_name == 'PRES_REL':
            attrs['applied_offset'] = np.float32(-14.7 * 0.689476)
        
        dataset.add_variable(
            name=var_name,
            data=data[var_name],
            dims=[time_dim],
            attrs=attrs,
        )
    
    # Global attributes
    dataset.set_attrs(
        {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "Seabird",
            "instrument_model": inst_header.get('instrument_model', 'SBE37'),
            "instrument_firmware": inst_header.get('instrument_firmware', ''),
            "instrument_serial_no": inst_header.get('instrument_serial_no', ''),
            "instrument_sample_interval": sample_interval,
            "parser": parser_name,
            "source_format": "dat_hex",
        }
    )
    
    return dataset


def _parse_instrument_header(header_lines: list[str]) -> dict[str, Any]:
    """Parse instrument header from SBE37-IM .DAT file.
    
    Mirrors MATLAB parseInstrumentHeader() function inside SBE37Parse.m
    Extracts metadata using regex patterns.
    
    Args:
        header_lines: Lines from //Status Information section
        
    Returns:
        Dictionary with parsed header information
    """
    header: dict[str, Any] = {}
    
    # Define regex patterns (from MATLAB)
    header_expr = r'SBE(\S+)\s+(\S+)\s+SERIAL NO.\s+(\d+)'
    mem_expr = r'samplenumber = (\d+), free = (\d+)'
    sample_expr = r'sample interval = (\d+) seconds'
    pressure_expr = r'PressureRange = (\d+)'
    output_expr = r'//Data Format: (\S+)'
    other_expr = r'([^\s=]+)\s*=\s*([^\s=]+)'
    
    for line in header_lines:
        # case 1: header (instrument model, firmware, serial)
        if match := re.search(header_expr, line):
            header['instrument_model'] = f'SBE{match.group(1)}'
            header['instrument_firmware'] = match.group(2)
            header['instrument_serial_no'] = match.group(3)
        
        # case 2: mem (sample number, free memory)
        elif match := re.search(mem_expr, line):
            header['numSamples'] = int(match.group(1))
            header['freeMem'] = int(match.group(2))
        
        # case 3: sample (sample interval)
        elif match := re.search(sample_expr, line):
            header['sampleInterval'] = int(match.group(1))
        
        # case 4: pressure (pressure range)
        elif match := re.search(pressure_expr, line):
            header['PressureRange'] = int(match.group(1))
        
        # case 5: output (output format like "tcpT")
        elif match := re.search(output_expr, line):
            header['outputFormat'] = match.group(1)
        
        # case 6: other (generic name=value pairs)
        elif match := re.search(other_expr, line):
            name = match.group(1)
            value = match.group(2)
            if value.endswith(','):
                value = value[:-1]
            header[name] = value
    
    return header


def _read_sbe37_hex(data_lines: list[str], inst_header: dict[str, Any]) -> dict[str, np.ndarray]:
    """Parse hex data lines from SBE37-IM .DAT file.
    
    Mirrors MATLAB readSBE37hex.m function.
    Reads hex data and converts to physical units.
    
    Args:
        data_lines: Hex data lines from //Begin Data section
        inst_header: Parsed instrument header
        
    Returns:
        Dictionary with converted data (TEMP, CNDC, PRES_REL, TIME)
    """
    output_format = inst_header.get('outputFormat', 'tcpT')
    
    # Find positions of each field in the output format
    # Mirrors: temperature = [find(...), find(...)]
    temp_pos = _find_field_position(output_format, 't')
    cond_pos = _find_field_position(output_format, 'c')
    pres_pos = _find_field_position(output_format, 'p')
    time_pos = _find_field_position(output_format, 'T')
    
    n_lines = len(data_lines)
    
    # Preallocate arrays (mirrors preallocZeros = zeros(nLines, 1))
    temperature = np.zeros(n_lines, dtype=np.uint32)
    conductivity = np.zeros(n_lines, dtype=np.uint32)
    pressure = np.zeros(n_lines, dtype=np.uint16) if pres_pos else None
    time_raw = np.zeros(n_lines, dtype=np.uint32)
    
    # Read hex data (mirrors: for k = 1:length(dataLines))
    for k, line in enumerate(data_lines):
        # Temperature (6 hex chars)
        if temp_pos:
            temperature[k] = int(line[temp_pos[0]:temp_pos[1]], 16)
        
        # Conductivity (6 hex chars)
        if cond_pos:
            conductivity[k] = int(line[cond_pos[0]:cond_pos[1]], 16)
        
        # Pressure (4 hex chars, byte-swapped)
        # Mirrors: swapbytes(uint16(hex2dec(...)))
        if pres_pos and pressure is not None:
            hex_val = int(line[pres_pos[0]:pres_pos[1]], 16)
            # Swap bytes: convert to uint16 and swap
            pressure[k] = ((hex_val & 0xFF) << 8) | ((hex_val & 0xFF00) >> 8)
        
        # Time (8 hex chars, byte-swapped)
        # Mirrors: swapbytes(uint32(hex2dec(...)))
        if time_pos:
            hex_val = int(line[time_pos[0]:time_pos[1]], 16)
            # Swap bytes for uint32
            time_raw[k] = (
                ((hex_val & 0x000000FF) << 24) |
                ((hex_val & 0x0000FF00) << 8) |
                ((hex_val & 0x00FF0000) >> 8) |
                ((hex_val & 0xFF000000) >> 24)
            )
    
    # Convert to physical units (mirrors convertData)
    data = _convert_data(temperature, conductivity, pressure, time_raw, inst_header)
    
    return data


def _find_field_position(output_format: str, field_char: str) -> tuple[int, int] | None:
    """Find start and end slice position of a field in the hex output format.

    Mirrors MATLAB readSBE37hex: the ``//Data Format`` string contains one
    character per hex nibble (e.g. ``ttttttccccccppppTTTTTTTT``), and each
    field spans from the first to the last occurrence of its letter:
        field = [find(outputFormat==ch, 1, 'first'), find(outputFormat==ch, 1, 'last')]

    Args:
        output_format: Format string from the ``//Data Format`` header line
        field_char: Character to find ('t', 'c', 'p', 'T')

    Returns:
        Tuple of (start_index, end_index) for Python slicing, or None if the
        field is not present.
    """
    indices = [i for i, ch in enumerate(output_format) if ch == field_char]
    if not indices:
        return None
    # MATLAB line(first:last) is 1-based inclusive -> Python slice [first, last+1]
    return (indices[0], indices[-1] + 1)


def _convert_data(
    temperature: np.ndarray,
    conductivity: np.ndarray,
    pressure: np.ndarray | None,
    time_raw: np.ndarray,
    inst_header: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Convert raw hex data to IMOS compliant parameters.
    
    Mirrors MATLAB convertData() function in readSBE37hex.m
    
    Args:
        temperature: Raw temperature values (uint32)
        conductivity: Raw conductivity values (uint32)
        pressure: Raw pressure values (uint16) or None
        time_raw: Raw time values (uint32)
        inst_header: Instrument header with calibration info
        
    Returns:
        Dictionary with TEMP, CNDC, PRES_REL, TIME
    """
    data: dict[str, np.ndarray] = {}
    
    # Temperature: raw/10000 - 10 (degrees Celsius)
    # Mirrors: newData.TEMP = data.temperature/10000 - 10
    data['TEMP'] = temperature.astype(float) / 10000.0 - 10.0
    
    # Conductivity: raw/100000 - 0.5 (Siemens/meter)
    # Mirrors: newData.CNDC = data.conductivity/100000 - 0.5
    data['CNDC'] = conductivity.astype(float) / 100000.0 - 0.5
    
    # Pressure: scale based on pressure range
    if pressure is not None:
        pressure_range = inst_header.get('PressureRange', 0)
        # Convert psia range to dbar range
        # Mirrors: pressureRangeInDbar = 0.6894757 * (header.PressureRange - 14.7)
        pressure_range_dbar = 0.6894757 * (pressure_range - 14.7)
        # Pressure in dbar (relative to ocean surface)
        # Mirrors: newData.PRES_REL = (data.pressure * pressureRangeInDbar /(0.85*65536)) - (0.05*pressureRangeInDbar)
        data['PRES_REL'] = (
            pressure.astype(float) * pressure_range_dbar / (0.85 * 65536)
        ) - (0.05 * pressure_range_dbar)
    
    # Time: seconds since "2000-01-00" -> MATLAB datenum.
    # Mirrors readSBE37hex: TIME = data.time/(3600*24) + datenum('2000-01-00')
    # datenum('2000-01-00 00:00:00') == 730485 (day 0 of Jan 2000).
    epoch_2000 = 730485  # MATLAB datenum for '2000-01-00'
    data['TIME'] = (time_raw.astype(float) / (3600 * 24)) + epoch_2000
    
    return data

