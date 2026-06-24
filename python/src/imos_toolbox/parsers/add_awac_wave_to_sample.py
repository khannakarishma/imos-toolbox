"""Add AWAC wave data to sample_data structure.

Integrates wave data from ASCII files into IMOS dataset format.

Mirrors MATLAB addAWACWaveToSample.m implementation.

Author: Kiro AI Assistant
Based on MATLAB implementation by Guillaume Galibert
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re

import numpy as np

from imos_toolbox.model import IMOSDataset


def add_awac_wave_to_sample(
    sample_data: IMOSDataset,
    wave_data: dict[str, Any],
    filename: Path | str
) -> list[IMOSDataset]:
    """Add AWAC wave data to sample_data, returning list of two datasets.
    
    Creates a second dataset for wave data, since wave timestamps differ
    from velocity/sensor data timestamps.
    
    Mirrors MATLAB addAWACWaveToSample.m function.
    
    Args:
        sample_data: Existing IMOSDataset with velocity/sensor data
        wave_data: Dictionary from read_awac_wave_ascii()
        filename: Path to original .wpr file
        
    Returns:
        List of two IMOSDatasets:
            [0] = Original velocity/sensor data
            [1] = Wave data
    """
    filename = Path(filename)
    file_path = filename.parent
    file_rad_name = filename.stem
    wave_filename = file_path / f"{file_rad_name}.wap"
    
    # Create wave dataset as copy of original (shares metadata)
    wave_dataset = IMOSDataset.empty()
    
    # Update metadata for wave dataset
    wave_dataset.set_attrs({
        'toolbox_input_file': str(wave_filename),
        'featureType': '',
        'instrument_make': sample_data.dataset.attrs.get('instrument_make', 'Nortek'),
        'instrument_model': sample_data.dataset.attrs.get('instrument_model', 'AWAC'),
        'instrument_serial_no': sample_data.dataset.attrs.get('instrument_serial_no', ''),
        'instrument_firmware': sample_data.dataset.attrs.get('instrument_firmware', ''),
        'beam_angle': sample_data.dataset.attrs.get('beam_angle', 25.0),
    })
    
    # Calculate sample interval
    time_diff = np.diff(wave_data['Time'] * 24 * 3600)
    instrument_sample_interval = float(np.median(time_diff))
    wave_dataset.set_attrs({'instrument_sample_interval': instrument_sample_interval})
    
    # Extract averaging interval from summary if available
    avg_interval = None
    if 'summary' in wave_data:
        # Find number of samples and sampling rate
        n_samples = None
        sampling_rate = None
        
        for line in wave_data['summary']:
            match = re.search(r'Wave\s+-\s+Number\s+of\s+samples\s+(\d+)', line)
            if match:
                n_samples = int(match.group(1))
            
            match = re.search(r'Wave\s+-\s+Sampling\s+rate\s+([\d\.]+)\s+Hz', line)
            if match:
                sampling_rate = float(match.group(1))
        
        if n_samples and sampling_rate:
            avg_interval = n_samples / sampling_rate
    
    if avg_interval:
        wave_dataset.set_attrs({'instrument_average_interval': avg_interval})
        avg_interval_str = str(avg_interval)
    else:
        avg_interval_str = '?'
    
    # Determine magnetic correction suffix
    mag_ext = '_MAG' if not wave_data.get('isMagBias', False) else ''
    mag_bias_comment = wave_data.get('magBiasComment', '')
    mag_dec = wave_data.get('magDec', 0.0)
    
    # Add TIME dimension
    time_comment = (
        f'Time stamp corresponds to the start of the measurement which lasts '
        f'{avg_interval_str} seconds.'
    )
    wave_dataset.add_dimension('TIME', wave_data['Time'], attrs={'comment': time_comment})
    
    # Add frequency dimensions
    wave_dataset.add_dimension('FREQUENCY_1', wave_data['pwrFrequency'])
    wave_dataset.add_dimension('FREQUENCY_2', wave_data['dirFrequency'])
    
    # Add direction dimension
    direction_attrs = {}
    if mag_bias_comment:
        direction_attrs['comment'] = mag_bias_comment
    wave_dataset.add_dimension(f'DIR{mag_ext}', wave_data['Direction'], attrs=direction_attrs)
    
    # Add scaffold variables
    wave_dataset.add_variable('TIMESERIES', data=np.int32(1), dims=[])
    wave_dataset.add_variable('LATITUDE', data=np.float64(np.nan), dims=[])
    wave_dataset.add_variable('LONGITUDE', data=np.float64(np.nan), dims=[])
    wave_dataset.add_variable('NOMINAL_DEPTH', data=np.float32(np.nan), dims=[])
    
    # Determine coordinates for surface vs depth variables
    coords_surface = 'TIME LATITUDE LONGITUDE'  # Wave data at surface
    coords_depth = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'  # Sensor data
    
    # Add wave spectra
    wave_dataset.add_variable(
        'VDEN',
        data=wave_data['pwrSpectrum'],
        dims=['TIME', 'FREQUENCY_1'],
        attrs={'coordinates': coords_surface}
    )
    
    wave_dataset.add_variable(
        f'SSWD{mag_ext}',
        data=wave_data['dirSpectrum'],
        dims=['TIME', 'FREQUENCY_2'],
        attrs={'coordinates': coords_surface}
    )
    
    # Add wave parameters
    wave_params = [
        ('WSSH', 'SignificantHeight', coords_surface),  # Significant height (Hm0)
        ('WPPE', 'PeakPeriod', coords_surface),  # Peak period (Tp)
        ('WPMH', 'MeanZeroCrossingPeriod', coords_surface),  # Mean zero-crossing period (Tz)
        (f'WPDI{mag_ext}', 'PeakDirection', coords_surface),  # Peak direction
        (f'SSDS{mag_ext}', 'DirectionalSpread', coords_surface),  # Directional spread
        (f'VDIR{mag_ext}', 'MeanDirection', coords_surface),  # Mean direction
    ]
    
    for var_name, data_key, coords in wave_params:
        attrs = {'coordinates': coords}
        if mag_ext == '' and any(x in var_name for x in ['WPDI', 'SSDS', 'VDIR']):
            attrs['compass_correction_applied'] = mag_dec
            if mag_bias_comment:
                attrs['comment'] = mag_bias_comment
        
        wave_dataset.add_variable(
            var_name,
            data=wave_data[data_key],
            dims=['TIME'],
            attrs=attrs
        )
    
    # Add extended wave parameters if present (31-column format)
    if 'SpectraType' in wave_data:
        extended_params = [
            ('WHTH', 'MeanOneThirdHeight', coords_surface),  # Mean 1/3 height
            ('WHTE', 'MeanOneTenthHeight', coords_surface),  # Mean 1/10 height
            ('WMXH', 'MaximumHeight', coords_surface),  # Maximum height
            ('WMSH', 'MeanHeight', coords_surface),  # Mean height
            ('WPSM', 'MeanPeriod', coords_surface),  # Mean period (Tm02)
            ('WPTH', 'MeanOneThirdPeriod', coords_surface),  # Mean 1/3 period
            ('WPTE', 'MeanOneTenthPeriod', coords_surface),  # Mean 1/10 period
            ('WMPP', 'MaximumPeriod', coords_surface),  # Maximum period
        ]
        
        for var_name, data_key, coords in extended_params:
            wave_dataset.add_variable(
                var_name,
                data=wave_data[data_key],
                dims=['TIME'],
                attrs={'coordinates': coords}
            )
        
        # Add spectrum type
        wave_dataset.add_variable(
            'SPCT',
            data=wave_data['SpectraType'],
            dims=['TIME'],
            attrs={'coordinates': coords_surface}
        )
    
    # Add scalar variables (sensor data)
    wave_dataset.add_variable(
        'TEMP',
        data=wave_data['Temperature'],
        dims=['TIME'],
        attrs={'coordinates': coords_depth}
    )
    
    wave_dataset.add_variable(
        'PRES_REL',
        data=wave_data['MeanPressure'],
        dims=['TIME'],
        attrs={'coordinates': coords_depth}
    )
    
    wave_dataset.add_variable(
        'BAT_VOLT',
        data=wave_data['Battery'],
        dims=['TIME'],
        attrs={'coordinates': coords_depth}
    )
    
    # Add heading with potential magnetic correction
    heading_attrs = {'coordinates': coords_depth}
    if mag_ext == '':
        heading_attrs['compass_correction_applied'] = mag_dec
        if mag_bias_comment:
            heading_attrs['comment'] = mag_bias_comment
    
    wave_dataset.add_variable(
        f'HEADING{mag_ext}',
        data=wave_data['Heading'],
        dims=['TIME'],
        attrs=heading_attrs
    )
    
    wave_dataset.add_variable(
        'PITCH',
        data=wave_data['Pitch'],
        dims=['TIME'],
        attrs={'coordinates': coords_depth}
    )
    
    wave_dataset.add_variable(
        'ROLL',
        data=wave_data['Roll'],
        dims=['TIME'],
        attrs={'coordinates': coords_depth}
    )
    
    # Add full spectrum (3D: time x frequency x direction)
    full_spectrum_attrs = {'coordinates': coords_surface}
    if mag_ext == '':
        full_spectrum_attrs['compass_correction_applied'] = mag_dec
        if mag_bias_comment:
            full_spectrum_attrs['comment'] = mag_bias_comment
    
    wave_dataset.add_variable(
        f'SSWV{mag_ext}',
        data=wave_data['fullSpectrum'],
        dims=['TIME', 'FREQUENCY_2', f'DIR{mag_ext}'],
        attrs=full_spectrum_attrs
    )
    
    # Return list of two datasets: [velocity/sensor, wave]
    return [sample_data, wave_dataset]
