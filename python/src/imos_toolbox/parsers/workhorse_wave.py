"""Workhorse ADCP wave data ASCII reader.

Reads processed wave data from WavesMon ASCII text files (.WVS, _LOG9.txt, DSpec*.txt, etc.).
Mirrors MATLAB readWorkhorseWaveAscii.m implementation.

Author: Kiro AI Assistant
Based on MATLAB implementation by Guillaume Galibert
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


def read_workhorse_wave_ascii(filename: Path) -> dict[str, Any]:
    """Read RDI Workhorse wave data from processed wave text files.
    
    Reads wave data exported by WavesMon software from RDI Workhorse ADCPs.
    Expects files:
    - *_LOG9.TXT: Wave parameters time series
    - DSpec*.txt: Directional spectra
    - PSpec*.txt: Pressure spectra
    - SSpec*.txt: Surface elevation spectra
    - VSpec*.txt: Velocity spectra
    - *.txt: Summary file (optional)
    
    Mirrors MATLAB readWorkhorseWaveAscii.m function.
    
    Args:
        filename: Path to wave data file (typically .WVS binary file)
                  ASCII files located in same directory
                  
    Returns:
        Dictionary with wave data:
            - summary: List of summary text lines (if file exists)
            - param: Dictionary with time series parameters:
                - time: MATLAB datenum format
                - Hs, Tp, Dp: Significant wave height, period, direction
                - Tp_W, Dp_W, Hs_W: Wind wave parameters
                - Tp_S, Dp_S, Hs_S: Swell wave parameters
                - ht, Hmax, Tmax, Hth, Tth, Hmn, Tmn, Hte, Tte, Dmn
            - Dspec: Directional spectrum (time × freq × dir)
            - Pspec: Pressure spectrum (time × freq)
            - Sspec: Surface elevation spectrum (time × freq)
            - Vspec: Velocity spectrum (time × freq)
    
    Raises:
        ValueError: If required files not found
    """
    file_path = Path(filename).parent
    file_name = Path(filename).stem
    
    wave_data: dict[str, Any] = {}
    
    # Read summary file (optional)
    summary_file = file_path / f"{file_name}.txt"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            wave_data['summary'] = f.readlines()
    
    # Load *_LOG9.TXT file (required)
    log_files = list(file_path.glob("*_LOG9.TXT"))
    if len(log_files) == 0:
        raise ValueError(f"No *_LOG9.TXT file found in {file_path}")
    
    log_file = log_files[0]
    data = np.loadtxt(log_file, delimiter=',')
    
    # Extract time
    years = data[:, 1] + 2000
    months = data[:, 2]
    days = data[:, 3]
    hours = data[:, 4]
    minutes = data[:, 5]
    seconds = data[:, 6]
    hundredths = data[:, 7]
    
    # Convert to MATLAB datenum
    time = np.zeros(len(years))
    for i in range(len(years)):
        try:
            dt = datetime(
                int(years[i]),
                int(months[i]),
                int(days[i]),
                int(hours[i]),
                int(minutes[i]),
                int(seconds[i]),
                int(hundredths[i]) * 10000  # Convert to microseconds
            )
            # Convert to MATLAB datenum (days since 0000-01-01)
            ordinal = dt.toordinal()
            frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
            time[i] = ordinal + 366 + frac  # MATLAB epoch offset
        except (ValueError, OverflowError):
            time[i] = np.nan
    
    # Extract wave parameters (columns 9 onwards)
    wave_data['param'] = {
        'time': time,
        'Hs': data[:, 8],
        'Tp': data[:, 9],
        'Dp': data[:, 10],
        'Tp_W': data[:, 11],
        'Dp_W': data[:, 12],
        'Hs_W': data[:, 13],
        'Tp_S': data[:, 14],
        'Dp_S': data[:, 15],
        'Hs_S': data[:, 16],
        'ht': data[:, 17],
        'Hmax': data[:, 18],
        'Tmax': data[:, 19],
        'Hth': data[:, 20],
        'Tth': data[:, 21],
        'Hmn': data[:, 22],
        'Tmn': data[:, 23],
        'Hte': data[:, 24],
        'Tte': data[:, 25],
        'Dmn': data[:, 26],
    }
    
    # Replace WavesMon bad data indicators (-1, -32768) with NaN
    for key in wave_data['param']:
        if key != 'time':
            param_data = wave_data['param'][key]
            param_data[param_data == -1] = np.nan
            param_data[param_data == -32768] = np.nan
    
    # Read spectra files
    spec_types = ['D', 'P', 'S', 'V']
    for spec_type in spec_types:
        spec_files = sorted(file_path.glob(f"{spec_type}Spec*.txt"))
        
        if len(spec_files) == 0:
            raise ValueError(f"No {spec_type}Spec*.txt files found in {file_path}")
        
        spec_name = f"{spec_type}spec"
        wave_data[spec_name] = {'time': [], 'data': []}
        
        for spec_file in spec_files:
            # Extract time from filename (e.g., DSpec202112151030.txt -> 202112151030)
            time_str = spec_file.stem[5:]  # Remove 'DSpec' prefix
            file_time = datetime.strptime('20' + time_str + '0', '%Y%m%d%H%M')
            
            # Convert to MATLAB datenum
            ordinal = file_time.toordinal()
            frac = (file_time - datetime(file_time.year, file_time.month, file_time.day)).total_seconds() / 86400.0
            file_time_num = ordinal + 366 + frac
            
            if spec_type == 'D':
                # Directional spectrum - need metadata from first file
                if len(wave_data[spec_name]['time']) == 0:
                    # Read metadata from header
                    with open(spec_file, 'r') as f:
                        lines = f.readlines()
                        
                        # Line 3: nDir and nFreq
                        info_dim = lines[2].split()
                        n_dir = int(info_dim[1])
                        n_freq = int(info_dim[3])
                        
                        # Line 5: frequency info
                        info_freq = lines[4].split()
                        freq_step = float(info_freq[4])
                        first_freq = float(info_freq[11])
                        
                        # Create frequency and direction arrays
                        wave_data[spec_name]['freq'] = np.arange(first_freq, first_freq + n_freq * freq_step, freq_step)
                        wave_data[spec_name]['dir'] = np.arange(0, 360, 360 / n_dir)
                        wave_data[spec_name]['nDir'] = n_dir
                        wave_data[spec_name]['nFreq'] = n_freq
                
                # Get first direction slice from line 6
                with open(spec_file, 'r') as f:
                    lines = f.readlines()
                    info_dir = lines[5].split()
                    first_dir_slice = int(info_dir[7])
                
                # Create direction array for this file
                direction = np.arange(first_dir_slice, first_dir_slice + 360, 360 / n_dir)
                direction[direction >= 360] -= 360
                
                # Add negative value for interpolation at 0
                direction = np.append(direction, direction[0] - 360 / n_dir)
                
                # Load data
                data = np.loadtxt(spec_file)
                data[data == 0] = np.nan
                
                # Add last column (copy of first) for interpolation
                data = np.column_stack([data, data[:, np.argmax(direction[:-1] == np.max(direction[:-1]))]])
                
                # Interpolate to fixed directions
                interp_data = np.zeros((n_freq, n_dir))
                for i in range(n_freq):
                    interp_data[i, :] = np.interp(wave_data[spec_name]['dir'], direction, data[i, :])
                
                wave_data[spec_name]['time'].append(file_time_num)
                if 'data' not in wave_data[spec_name] or len(wave_data[spec_name]['data']) == 0:
                    wave_data[spec_name]['data'] = [interp_data]
                else:
                    wave_data[spec_name]['data'].append(interp_data)
            else:
                # Non-directional spectra (P, S, V)
                data = np.loadtxt(spec_file)
                data[data == 0] = np.nan
                
                wave_data[spec_name]['time'].append(file_time_num)
                wave_data[spec_name]['data'].append(data)
        
        # Convert lists to numpy arrays
        wave_data[spec_name]['time'] = np.array(wave_data[spec_name]['time'])
        if spec_type == 'D':
            wave_data[spec_name]['data'] = np.array(wave_data[spec_name]['data'])
        else:
            wave_data[spec_name]['data'] = np.array(wave_data[spec_name]['data'])
    
    # Synchronize spectra times with param times
    # Some spectra may have different time lengths than LOG9.txt
    n_times = len(wave_data['param']['time'])
    
    for spec_type in spec_types:
        spec_name = f"{spec_type}spec"
        n_spec_time = len(wave_data[spec_name]['time'])
        
        if n_spec_time < n_times:
            # Spectra time shorter than LOG9.txt - map to matching times
            print(f"Fixing short {spec_name} time ({n_spec_time} < {n_times})")
            
            # Find matching times (within tolerance)
            old_time = wave_data[spec_name]['time']
            old_data = wave_data[spec_name]['data']
            
            # Create new arrays with NaN for missing times
            new_time = wave_data['param']['time']
            if spec_type == 'D':
                new_data = np.full((n_times, *old_data.shape[1:]), np.nan)
            else:
                new_data = np.full((n_times, *old_data.shape[1:]), np.nan)
            
            # Match times and copy data
            for i, t in enumerate(old_time):
                # Find closest time in param.time
                idx = np.argmin(np.abs(wave_data['param']['time'] - t))
                if np.abs(wave_data['param']['time'][idx] - t) < 1e-4:  # Within ~10 seconds
                    new_data[idx] = old_data[i]
            
            wave_data[spec_name]['time'] = new_time
            wave_data[spec_name]['data'] = new_data
            
        elif n_spec_time > n_times:
            print(f"Warning: {spec_name} time is longer than LOG9.txt time ({n_spec_time} > {n_times})")
    
    return wave_data
