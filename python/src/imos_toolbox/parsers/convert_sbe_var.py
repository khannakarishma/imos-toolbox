"""SeaBird to IMOS variable name and unit conversion.

Maps raw SeaBird variable names from CNV files to IMOS standard parameter names
and applies unit conversions where necessary.

Python port of MATLAB's convertSBEcnvVar.m
Author: Guillaume Galibert (MATLAB original)
Ported to Python for IMOS Toolbox Python port
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np


def convert_sbe_var(
    name: str,
    data: np.ndarray,
    time_offset: float = 0.0,
    mode: str = 'timeSeries',
    inst_header: dict[str, Any] | None = None,
    proc_header: dict[str, Any] | None = None,
) -> tuple[str, np.ndarray, str]:
    """Convert SeaBird variable name and data to IMOS standard.
    
    Python port of MATLAB convertSBEcnvVar.m function.
    
    Args:
        name: Raw SeaBird variable name from CNV file
        data: Variable data array
        time_offset: MATLAB datenum offset for TIME variables
        mode: 'timeSeries' or 'profile'
        inst_header: Parsed instrument header metadata (optional)
        proc_header: Parsed processed header metadata (optional)
        
    Returns:
        Tuple of (imos_name, converted_data, comment)
        Returns ('', empty_array, '') if variable should be skipped
    """
    # TIME conversions - elapsed time in various units
    if name == 'timeS':  # seconds since start
        return 'TIME', data / 86400 + time_offset, ''
    
    elif name == 'timeM':  # minutes since start
        return 'TIME', data / 1440 + time_offset, ''
    
    elif name == 'timeH':  # hours since start
        return 'TIME', data / 24 + time_offset, ''
    
    elif name == 'timeJ':  # days since start of year (Julian)
        # Mirrors MATLAB convertSBEcnvVar: clumsy fallback uses the datenum
        # VALUE 2010 (-> year 0005), not the calendar year 2010.
        if time_offset == 0:
            time_offset = 2010
        start_year = datetime.fromordinal(int(time_offset) - 366).year
        converted = data + matlab_datenum(datetime(start_year - 1, 12, 31))
        return 'TIME', converted, ''
    
    elif name == 'timeK':  # seconds since 01-Jan-2000
        epoch_2000 = matlab_datenum(datetime(2000, 1, 1))
        return 'TIME', data / 86400 + epoch_2000, ''
    
    elif name == 'timeY':  # seconds since 1970-01-01 (Unix epoch)
        epoch_1970 = matlab_datenum(datetime(1970, 1, 1))
        return 'TIME', data / 86400 + epoch_1970, ''
    
    # Pressure - strain gauge (dbar)
    elif name in ('pr', 'prM', 'prdM', 'prDM', 'prSM'):
        return 'PRES_REL', data, ''
    
    elif name == 'prdE':  # Pressure in psi -> convert to dbar
        return 'PRES_REL', data * 0.68948, ''
    
    # Temperature (deg C)
    elif name in ('t090C', 'tv290C', 't090'):
        return 'TEMP', data, ''
    
    # Conductivity (S/m)
    elif name in ('c0S0x2Fm', 'cond0S0x2Fm'):
        return 'CNDC', data, ''
    
    elif name in ('c0ms0x2Fcm', 'cond0ms0x2Fcm', 'c0mS0x2Fcm', 'cond0mS0x2Fcm'):
        return 'CNDC', data / 10, ''  # mS/cm -> S/m
    
    elif name in ('c0us0x2Fcm', 'cond0us0x2Fcm', 'c0uS0x2Fcm', 'cond0uS0x2Fcm'):
        return 'CNDC', data / 10000, ''  # uS/cm -> S/m
    
    # Fluorescence/Chlorophyll (ug/l or mg/m3)
    elif name == 'flC':
        return 'CPHL', data, 'Fluorescence WET Labs ECO-AFL/FL, Seapoint Chlorophyll Fluorometer (Ex: 430nm, Em: 685nm)'
    
    elif name == 'flCUVA':
        comment = 'Aquatracka III fluorescence (Ex: 430nm, Em: 685nm) - Warning: Assumed aquatracka UV namespace was used for Aquatracka III'
        return 'CPHL', data, comment
    
    elif name == 'flECO0x2DAFL':
        return 'CPHL', data, 'Fluorescence WET Labs ECO-AFL/FL (Ex: 470nm, Em: 695nm)'
    
    # PAR - Photosynthetically Active Radiation
    elif name in ('par0x2Fsat0x2Flog', 'par/sat/log', 'par0x2Flog'):
        return 'PAR', data, 'PAR/Logarithmic/ Satlantic'
    
    elif name == 'par':
        return 'PAR', data, ''
    
    elif name == 'cpar':
        return 'CPAR', data, ''
    
    # Oxygen - various units
    elif name == 'sbeox0Mg0x2FL':
        return 'DOXY', data, ''  # mg/l
    
    elif name == 'sbeox0ML0x2FL':
        return 'DOX', data, ''  # ml/l
    
    elif name == 'sbeox0Mm0x2FL':
        return 'DOX1', data, ''  # umol/L
    
    elif name in ('sbeox0Mm0x2FKg', 'sbeopoxMm0x2FKg'):
        return 'DOX2', data, ''  # umol/Kg
    
    elif name in ('sbeopoxPS', 'sbeox0PS'):
        return 'DOXS', data, ''  # % saturation
    
    elif name == 'sbeoxTC':
        return 'DOXY_TEMP', data, ''  # Oxygen Temperature
    
    # Salinity (PSU)
    elif name == 'sal00':
        return 'PSAL', data, ''
    
    # Beam Attenuation
    elif name in ('bat', 'CStarAt0'):
        return 'BAT', data, ''
    
    elif name == 'CStarTr0':
        return 'BAT_PERCENT', data, 'Beam Transmission, WET Labs C-Star [%]'
    
    # Turbidity (NTU)
    elif name in ('obs', 'obs30x2B', 'turbWETntu0', 'upoly0'):
        return 'TURB', data, ''
    
    # Descent rate (m/s)
    elif name == 'dz0x2FdtM':
        return 'DESC', data, ''
    
    # Density (kg/m3)
    elif name == 'density00':
        return 'DENS', data, ''
    
    # Depth (m)
    elif name in ('depSM', 'depFM'):
        return 'DEPTH', data, ''
    
    # Altimeter (m)
    elif name == 'altM':
        return 'ALTIMETER', data, ''
    
    # Position
    elif name == 'latitude':
        return 'LATITUDE_CAST', data, ''
    
    elif name == 'longitude':
        return 'LONGITUDE_CAST', data, ''
    
    # Acceleration (m/s^2)
    elif name == 'accM':
        return 'ACCELERATION', data, ''
    
    # Mode-specific variables (profile only)
    elif name == 'f1' and mode == 'profile':
        return 'CNDC_FREQ', data, 'Conductivity Frequency in Hz (added for minCondFreq detection)'
    
    elif name == 'flag' and mode == 'profile':
        return 'SBE_FLAG', data, 'SBE Processing Flag (added for binning). 0 is good, anything else bad.'
    
    elif name == 'scan' and mode == 'profile':
        return 'ETIME', data / 4, 'Elapsed time in seconds (basically number of scan divided by 4Hz, added for surface soak)'
    
    # Voltage channels (v0-v7) - try to map to sensor names
    elif name.startswith('v') and len(name) == 2 and name[1].isdigit():
        return _convert_voltage(name, data, inst_header, proc_header)
    
    # Unknown variable - skip it
    else:
        return '', np.array([]), ''


def _convert_voltage(
    name: str,
    data: np.ndarray,
    inst_header: dict[str, Any] | None,
    proc_header: dict[str, Any] | None,
) -> tuple[str, np.ndarray, str]:
    """Convert voltage channel to named sensor if possible.
    
    Args:
        name: Voltage channel name (v0-v7)
        data: Voltage data
        inst_header: Instrument header with sensor IDs and types
        proc_header: Processed header with voltage expressions
        
    Returns:
        Tuple of (imos_name, data, comment) or ('', empty, '') if not assigned
    """
    if inst_header is None or proc_header is None:
        return '', np.array([]), ''
    
    sensor_ids = inst_header.get('sensorIds', [])
    sensor_types = inst_header.get('sensorTypes', [])
    
    if not sensor_ids or not sensor_types:
        return '', np.array([]), ''
    
    # Map v0-v7 to "volt 0" through "volt 7"
    channel_num = name[1]
    volt_id = f'volt {channel_num}'
    
    # Find sensor type for this voltage channel
    sensor_type = 'not_assigned'
    for i, sid in enumerate(sensor_ids):
        if sid.lower() == volt_id.lower() and i < len(sensor_types):
            sensor_type = sensor_types[i]
            break
    
    if sensor_type == 'not_assigned':
        return '', np.array([]), ''
    
    # Clean sensor type to make valid variable name
    clean_type = ''.join(c if c.isalnum() else '_' for c in sensor_type)
    imos_name = f'volt_{clean_type}'
    
    # Get voltage comment from processed header
    volt_expr_key = f'volt{channel_num}Expr'
    comment = proc_header.get(volt_expr_key, '')
    
    return imos_name, data, comment


def matlab_datenum(dt: datetime) -> float:
    """Convert Python datetime to MATLAB datenum.
    
    MATLAB datenum is days since 0000-01-01 (proleptic Gregorian calendar).
    Python's toordinal is days since 0001-01-01.
    The offset is 366 days (MATLAB includes year 0 as a 366-day leap year).
    
    Args:
        dt: Python datetime object
        
    Returns:
        MATLAB datenum (float, days since 0000-01-01)
    """
    ordinal = dt.toordinal()
    fractional = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
    return ordinal + 366 + fractional
