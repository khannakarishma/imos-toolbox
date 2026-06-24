"""Nortek AWAC ADCP parser implementation.

Parses binary files from Nortek AWAC ADCP instruments (.wpr files).
Mirrors MATLAB awacParse.m implementation.

Author: Kiro AI Assistant
Based on MATLAB implementation by Paul McCarthy, Guillaume Galibert
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.parsers.read_paradopp_binary import read_paradopp_binary
from imos_toolbox.parsers.read_awac_wave_ascii import read_awac_wave_ascii
from imos_toolbox.parsers.add_awac_wave_to_sample import add_awac_wave_to_sample


class AWACParser(BaseParser):
    """Parser for Nortek AWAC ADCP binary files.
    
    Mirrors MATLAB awacParse.m implementation.
    
    Supports:
    - Binary .wpr format files
    - Beam and ENU coordinate systems
    - Processed and raw velocity data
    - Wave data (if .whd and .wap files present)
    
    Features:
    - Velocity data (UCUR, VCUR, WCUR or VEL1-3)
    - Echo intensity (ABSIC1-3)
    - Signal-to-noise ratio (SNR1-3) if processed
    - Temperature, pressure, heading, pitch, roll
    - Current speed and direction if processed
    """

    parser_name = "AWAC"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset | list[IMOSDataset]:
        """Parse AWAC ADCP binary file.
        
        If wave data files (.whd, .wap, .was, .wdr, .wds) are present in the same
        directory, they will be parsed and returned as a second dataset.
        
        Args:
            filenames: List of file paths (only first file used)
            mode: Data mode (timeSeries, profile, or empty string)
            
        Returns:
            IMOSDataset with parsed ADCP data, or list of two IMOSDatasets
            if wave data is present: [velocity/sensor_data, wave_data]
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("AWAC parser expects exactly one input file")

        source_file = file_list[0]
        
        # Read all structures from binary file
        structures = read_paradopp_binary(source_file)
        
        if not structures:
            raise ValueError(f"No structures found in {source_file}")
        
        # Extract configuration sections
        hardware = structures.get('Id5', [])
        head = structures.get('Id4', [])
        user = structures.get('Id0', [])
        
        if not hardware or not head or not user:
            raise ValueError("Missing required configuration sections (Id0, Id4, Id5)")
        
        hardware = hardware[0]  # Single record
        head = head[0]
        user = user[0]
        
        # Check for processed velocity data
        velocity_processed = 'Id106' in structures
        
        # Calculate distance values from metadata
        distance = self._calculate_distances(user, head)
        
        # Extract velocity data
        velocity_data = structures.get('Id32', [])
        if not velocity_data:
            raise ValueError("No velocity data found (Id32)")
        
        # Extract timestamps and sensor data
        time, sensor_data = self._extract_sensor_data(velocity_data)
        
        # Extract velocity and backscatter
        velocity, backscatter = self._extract_velocity_data(velocity_data)
        
        # Handle processed velocity if available
        if velocity_processed:
            processed_data = structures.get('Id106', [])
            velocity, derived_data = self._process_velocity_data(
                velocity_data, processed_data, velocity, time
            )
        else:
            derived_data = {}
        
        # Determine orientation and apply bad orientation filter
        orientation = self._determine_orientation(sensor_data['status'])
        distance = self._apply_orientation_to_distance(distance, orientation)
        
        velocity, backscatter, derived_data = self._filter_bad_orientation(
            velocity, backscatter, derived_data, sensor_data['status'], orientation
        )
        
        # Apply unit conversions
        sensor_data = self._convert_sensor_units(sensor_data)
        velocity = self._convert_velocity_units(velocity)
        
        if velocity_processed:
            derived_data = self._convert_derived_units(derived_data)
        
        # Create dataset
        dataset = self._create_dataset(
            source_file=source_file,
            time=time,
            distance=distance,
            velocity=velocity,
            backscatter=backscatter,
            sensor_data=sensor_data,
            derived_data=derived_data,
            user=user,
            head=head,
            hardware=hardware,
            velocity_processed=velocity_processed,
            orientation=orientation,
        )
        
        # Check for wave data files and add if present
        wave_data = read_awac_wave_ascii(source_file)
        
        if wave_data is not None:
            # Wave data present - return list of two datasets
            return add_awac_wave_to_sample(dataset, wave_data, source_file)
        
        # No wave data - return single dataset
        return dataset
    
    def _calculate_distances(self, user: dict, head: dict) -> np.ndarray:
        """Calculate distance along beams for each cell.
        
        Mirrors MATLAB distance calculation in awacParse.m
        """
        freq = head['Frequency']  # kHz
        blank_dist = user['T2']  # counts
        cell_size = user['BinLength']  # counts
        n_cells = user['NBins']
        
        # Frequency-dependent factor (mirrors MATLAB awacParse.m: default 0)
        if freq == 600:
            factor = 0.0797
        elif freq == 1000:
            factor = 0.0478
        else:
            factor = 0.0
        
        # Convert to meters
        cell_size = (cell_size / 256) * factor * np.cos(25 * np.pi / 180)
        blank_dist = blank_dist * 0.0229 * np.cos(25 * np.pi / 180) - cell_size
        
        # Calculate distances
        distance = blank_dist + np.arange(n_cells) * cell_size
        
        # Add half cell size (distance to middle of cell)
        distance = distance + cell_size
        
        return distance
    
    def _extract_sensor_data(self, velocity_data: list[dict]) -> tuple[np.ndarray, dict]:
        """Extract time and sensor data from velocity records."""
        time = np.array([record['Time'] for record in velocity_data])
        
        sensor_data = {
            'analn1': np.array([record['Analn1'] for record in velocity_data]),
            'battery': np.array([record['Battery'] for record in velocity_data]),
            'analn2': np.array([record['Analn2'] for record in velocity_data]),
            'heading': np.array([record['Heading'] for record in velocity_data]),
            'pitch': np.array([record['Pitch'] for record in velocity_data]),
            'roll': np.array([record['Roll'] for record in velocity_data]),
            'pressure_msb': np.array([record['PressureMSB'] for record in velocity_data]),
            'pressure_lsw': np.array([record['PressureLSW'] for record in velocity_data]),
            'temperature': np.array([record['Temperature'] for record in velocity_data]),
            'status': np.array([record['Status'] for record in velocity_data]),
        }
        
        # Combine pressure bytes
        sensor_data['pressure'] = (
            sensor_data['pressure_msb'].astype(np.uint32) * 65536 +
            sensor_data['pressure_lsw'].astype(np.uint32)
        )
        
        # Extract sound speed from analn2
        sensor_data['sound_speed'] = sensor_data['analn2']
        
        return time, sensor_data
    
    def _extract_velocity_data(self, velocity_data: list[dict]) -> tuple[dict, dict]:
        """Extract velocity and backscatter matrices."""
        velocity = {
            # Convert to float to allow NaN values
            'vel1': np.array([record['Vel1'] for record in velocity_data], dtype=np.float32),
            'vel2': np.array([record['Vel2'] for record in velocity_data], dtype=np.float32),
            'vel3': np.array([record['Vel3'] for record in velocity_data], dtype=np.float32),
        }
        
        backscatter = {
            # Convert to float to allow NaN values
            'amp1': np.array([record['Amp1'] for record in velocity_data], dtype=np.float32),
            'amp2': np.array([record['Amp2'] for record in velocity_data], dtype=np.float32),
            'amp3': np.array([record['Amp3'] for record in velocity_data], dtype=np.float32),
        }
        
        return velocity, backscatter
    
    def _process_velocity_data(
        self,
        raw_data: list[dict],
        processed_data: list[dict],
        velocity: dict,
        time: np.ndarray
    ) -> tuple[dict, dict]:
        """Handle processed velocity data.
        
        Replaces raw velocity with processed (tilt-corrected) velocity.
        """
        # Update velocity with processed data. MATLAB index-assigns into a
        # freshly created array, so unmatched timestamps remain 0 (not NaN).
        velocity['vel1'] = np.zeros_like(velocity['vel1'], dtype=np.float32)
        velocity['vel2'] = np.zeros_like(velocity['vel2'], dtype=np.float32)
        velocity['vel3'] = np.zeros_like(velocity['vel3'], dtype=np.float32)
        
        for i, record in enumerate(processed_data):
            # Find matching time index
            idx = np.where(time == record['Time'])[0]
            if len(idx) > 0:
                velocity['vel1'][idx[0], :] = record['Vel1']
                velocity['vel2'][idx[0], :] = record['Vel2']
                velocity['vel3'][idx[0], :] = record['Vel3']
        
        # Extract derived data (unmatched timestamps default to 0, per MATLAB)
        derived_data = {
            'snr1': np.zeros((len(time), len(processed_data[0]['Snr1'])), dtype=np.float32),
            'snr2': np.zeros((len(time), len(processed_data[0]['Snr2'])), dtype=np.float32),
            'snr3': np.zeros((len(time), len(processed_data[0]['Snr3'])), dtype=np.float32),
            'error_code1': np.zeros((len(time), len(processed_data[0]['Erc1'])), dtype=np.float32),
            'error_code2': np.zeros((len(time), len(processed_data[0]['Erc2'])), dtype=np.float32),
            'error_code3': np.zeros((len(time), len(processed_data[0]['Erc3'])), dtype=np.float32),
            'speed': np.zeros((len(time), len(processed_data[0]['speed'])), dtype=np.float32),
            'direction': np.zeros((len(time), len(processed_data[0]['direction'])), dtype=np.float32),
            'profile_error_code': np.zeros((len(time), len(processed_data[0]['profileErrorCode'])), dtype=np.float32),
            'qc_flag': np.zeros((len(time), len(processed_data[0]['qcFlag'])), dtype=np.float32),
        }
        
        for i, record in enumerate(processed_data):
            idx = np.where(time == record['Time'])[0]
            if len(idx) > 0:
                derived_data['snr1'][idx[0], :] = record['Snr1']
                derived_data['snr2'][idx[0], :] = record['Snr2']
                derived_data['snr3'][idx[0], :] = record['Snr3']
                derived_data['error_code1'][idx[0], :] = record['Erc1']
                derived_data['error_code2'][idx[0], :] = record['Erc2']
                derived_data['error_code3'][idx[0], :] = record['Erc3']
                derived_data['speed'][idx[0], :] = record['speed']
                derived_data['direction'][idx[0], :] = record['direction']
                derived_data['profile_error_code'][idx[0], :] = record['profileErrorCode']
                derived_data['qc_flag'][idx[0], :] = record['qcFlag']
        
        return velocity, derived_data
    
    def _determine_orientation(self, status: np.ndarray) -> int:
        """Determine ADCP orientation from status bytes.
        
        Mirrors MATLAB awacParse.m:
            adcpOrientations = bitget(status, 1)
            adcpOrientation = mode(adcpOrientations)
        where 1 == downward-looking, 0 == upward-looking.
        """
        # Bit 0 of status indicates orientation
        orientations = (status & 0x01).astype(np.uint8)
        
        # Most frequent value reflects the deployed orientation (MATLAB mode)
        vals, counts = np.unique(orientations, return_counts=True)
        orientation = int(vals[int(np.argmax(counts))])
        
        return orientation
    
    def _apply_orientation_to_distance(
        self,
        distance: np.ndarray,
        orientation: int
    ) -> np.ndarray:
        """Apply sign to distance based on orientation.
        
        Mirrors MATLAB awacParse.m: orientation==1 is a downward-looking ADCP,
        for which distance/height are negated.
        """
        if orientation == 1:
            # Downward looking - negative values
            return -distance
        else:
            # Upward looking - positive values
            return distance
    
    def _filter_bad_orientation(
        self,
        velocity: dict,
        backscatter: dict,
        derived_data: dict,
        status: np.ndarray,
        expected_orientation: int
    ) -> tuple[dict, dict, dict]:
        """Set data to NaN where orientation doesn't match expected."""
        orientations = (status & 0x01).astype(np.uint8)
        bad_mask = orientations != expected_orientation
        
        # Apply to velocity
        velocity['vel1'][bad_mask, :] = np.nan
        velocity['vel2'][bad_mask, :] = np.nan
        velocity['vel3'][bad_mask, :] = np.nan
        
        # Apply to backscatter
        backscatter['amp1'][bad_mask, :] = np.nan
        backscatter['amp2'][bad_mask, :] = np.nan
        backscatter['amp3'][bad_mask, :] = np.nan
        
        # Apply to derived data if present
        for key in derived_data:
            if derived_data[key].ndim == 2:
                derived_data[key][bad_mask, :] = np.nan
        
        return velocity, backscatter, derived_data
    
    def _convert_sensor_units(self, sensor_data: dict) -> dict:
        """Convert sensor data to standard units."""
        sensor_data['battery'] = sensor_data['battery'] / 10.0  # 0.1V -> V
        sensor_data['sound_speed'] = sensor_data['sound_speed'] / 10.0  # 0.1 m/s -> m/s
        sensor_data['heading'] = sensor_data['heading'] / 10.0  # 0.1 deg -> deg
        sensor_data['pitch'] = sensor_data['pitch'] / 10.0  # 0.1 deg -> deg
        sensor_data['roll'] = sensor_data['roll'] / 10.0  # 0.1 deg -> deg
        sensor_data['pressure'] = sensor_data['pressure'] / 1000.0  # mm -> m (assuming dbar)
        sensor_data['temperature'] = sensor_data['temperature'] / 100.0  # 0.01 deg -> deg
        
        return sensor_data
    
    def _convert_velocity_units(self, velocity: dict) -> dict:
        """Convert velocity from mm/s to m/s."""
        velocity['vel1'] = velocity['vel1'].astype(np.float32) / 1000.0
        velocity['vel2'] = velocity['vel2'].astype(np.float32) / 1000.0
        velocity['vel3'] = velocity['vel3'].astype(np.float32) / 1000.0
        
        return velocity
    
    def _convert_derived_units(self, derived_data: dict) -> dict:
        """Convert derived data units."""
        # Convert SNR from counts to dB: 20*log10(counts)
        derived_data['snr1'][derived_data['snr1'] == 0] = np.nan
        derived_data['snr2'][derived_data['snr2'] == 0] = np.nan
        derived_data['snr3'][derived_data['snr3'] == 0] = np.nan
        derived_data['snr1'] = 20 * np.log10(derived_data['snr1'])
        derived_data['snr2'] = 20 * np.log10(derived_data['snr2'])
        derived_data['snr3'] = 20 * np.log10(derived_data['snr3'])
        
        # Convert speed from mm/s to m/s
        derived_data['speed'] = derived_data['speed'] / 1000.0
        
        # Convert direction from 0.01 deg to deg
        derived_data['direction'] = derived_data['direction'] / 100.0
        
        return derived_data
    
    def _create_dataset(
        self,
        source_file: Path,
        time: np.ndarray,
        distance: np.ndarray,
        velocity: dict,
        backscatter: dict,
        sensor_data: dict,
        derived_data: dict,
        user: dict,
        head: dict,
        hardware: dict,
        velocity_processed: bool,
        orientation: int,
    ) -> IMOSDataset:
        """Create IMOS-compliant dataset from parsed data."""
        dataset = IMOSDataset.empty()
        
        # Add TIME dimension
        time_comment = (
            f'Time stamp corresponds to the start of the measurement which lasts '
            f'{user["AvgInterval"]} seconds.'
        )
        dataset.add_dimension('TIME', time, attrs={'comment': time_comment})
        # Middle-of-measurement info (mirrors MATLAB seconds_to_middle_of_measurement)
        dataset.dataset.coords['TIME'].attrs['seconds_to_middle_of_measurement'] = (
            user['AvgInterval'] / 2
        )
        
        # Add DIST_ALONG_BEAMS dimension
        dist_comment = (
            "Values correspond to the distance between the instrument's transducers and "
            "the centre of each cells. Nortek instrument data is not vertically bin-mapped "
            "(no tilt correction applied). Cells are lying parallel to the beams, at heights "
            "above sensor that vary with tilt."
        )
        dataset.add_dimension('DIST_ALONG_BEAMS', distance, attrs={'comment': dist_comment})
        
        # Add HEIGHT_ABOVE_SENSOR if processed
        if velocity_processed:
            height_comment = (
                "Values correspond to the distance between the instrument's transducers and "
                "the centre of each cells. Data has been vertically bin-mapped using Nortek Storm "
                "software 'Remove tilt effects' procedure. Cells have consistent heights above sensor in time."
            )
            dataset.add_dimension(
                'HEIGHT_ABOVE_SENSOR', distance.copy(), attrs={'comment': height_comment}
            )
        
        # Add scaffold variables
        dataset.add_variable('TIMESERIES', data=np.int32(1), dims=[])
        dataset.add_variable('LATITUDE', data=np.float64(np.nan), dims=[])
        dataset.add_variable('LONGITUDE', data=np.float64(np.nan), dims=[])
        dataset.add_variable('NOMINAL_DEPTH', data=np.float32(np.nan), dims=[])
        
        # Determine coordinate system and variable names
        coord_system = user['CoordSystem']
        # Velocity dimension is HEIGHT_ABOVE_SENSOR when processed, else
        # DIST_ALONG_BEAMS (mirrors MATLAB iDimVel; independent of frame).
        vel_dim = 'HEIGHT_ABOVE_SENSOR' if velocity_processed else 'DIST_ALONG_BEAMS'
        if coord_system == 0:  # ENU
            vel1_name = 'UCUR_MAG'
            vel2_name = 'VCUR_MAG'
            vel3_name = 'WCUR'
        elif coord_system == 2:  # Beam
            vel1_name = 'VEL1'
            vel2_name = 'VEL2'
            vel3_name = 'VEL3'
        else:
            raise ValueError(f"Unsupported coordinate system: {coord_system}")
        
        # Add velocity variables (MATLAB lists vel2, vel1, vel3 order)
        coords_vel = f'TIME LATITUDE LONGITUDE {vel_dim}'
        dataset.add_variable(vel2_name, data=velocity['vel2'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
        dataset.add_variable(vel1_name, data=velocity['vel1'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
        dataset.add_variable(vel3_name, data=velocity['vel3'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
        
        # Add backscatter variables
        coords_diag = 'TIME LATITUDE LONGITUDE DIST_ALONG_BEAMS'
        dataset.add_variable('ABSIC1', data=backscatter['amp1'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
        dataset.add_variable('ABSIC2', data=backscatter['amp2'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
        dataset.add_variable('ABSIC3', data=backscatter['amp3'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
        
        # Add sensor variables
        coords_ts = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        dataset.add_variable('TEMP', data=sensor_data['temperature'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('PRES_REL', data=sensor_data['pressure'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('BAT_VOLT', data=sensor_data['battery'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('SSPD', data=sensor_data['sound_speed'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('PITCH', data=sensor_data['pitch'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('ROLL', data=sensor_data['roll'], dims=['TIME'], attrs={'coordinates': coords_ts})
        dataset.add_variable('HEADING_MAG', data=sensor_data['heading'], dims=['TIME'], attrs={'coordinates': coords_ts})
        
        # Add derived variables if processed
        if velocity_processed:
            dataset.add_variable('SNR1', data=derived_data['snr1'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            dataset.add_variable('SNR2', data=derived_data['snr2'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            dataset.add_variable('SNR3', data=derived_data['snr3'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            dataset.add_variable('NORTEK_ERR1', data=derived_data['error_code1'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            dataset.add_variable('NORTEK_ERR2', data=derived_data['error_code2'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            dataset.add_variable('NORTEK_ERR3', data=derived_data['error_code3'], dims=['TIME', 'DIST_ALONG_BEAMS'], attrs={'coordinates': coords_diag})
            
            # CSPD/CDIR/profile error/QC are added whenever velocity is
            # processed, regardless of coordinate frame (mirrors MATLAB).
            dataset.add_variable('CSPD', data=derived_data['speed'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
            dataset.add_variable('CDIR_MAG', data=derived_data['direction'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
            dataset.add_variable('NORTEK_PROFILE_ERR', data=derived_data['profile_error_code'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
            dataset.add_variable('NORTEK_QC', data=derived_data['qc_flag'], dims=['TIME', vel_dim], attrs={'coordinates': coords_vel})
        
        # Set global attributes
        dataset.set_attrs({
            'toolbox_input_file': str(source_file),
            'featureType': '',
            'instrument_make': 'Nortek',
            'instrument_model': 'AWAC',
            'instrument_serial_no': hardware['SerialNo'],
            'instrument_firmware': hardware['FWversion'],
            'instrument_sample_interval': np.median(np.diff(time * 24 * 3600)),
            'instrument_average_interval': user['AvgInterval'],
            'beam_angle': 25.0,
            'beam_to_xyz_transform': head['TransformationMatrix'].tolist(),
            'parser': self.parser_name,
        })
        
        return dataset
