"""Teledyne RDI Workhorse ADCP parser implementation.

Parses binary PD0 format files from Workhorse ADCP instruments.
Mirrors MATLAB workhorseParse.m implementation.

Author: Kiro AI Assistant
Based on MATLAB implementation by Paul McCarthy, Charles James, Guillaume Galibert, et al.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.parsers.workhorse_binary import read_workhorse_ensembles
from imos_toolbox.parsers.workhorse_wave import read_workhorse_wave_ascii
from imos_toolbox.parsers.workhorse_utils import (
    WorkhorseMetadata,
    convert_workhorse_time,
    calculate_cell_distances,
    create_velocity_variables,
    create_beam_variables,
    create_timeseries_variables,
    apply_missing_value_filter,
    apply_bad_orientation_filter,
)


class WorkhorseParser(BaseParser):
    """Parser for Teledyne RDI Workhorse ADCP binary files.
    
    Mirrors MATLAB workhorseParse.m implementation.
    
    Supports:
    - Binary PD0 format files (.000, .PD0, etc.)
    - Beam coordinate frame
    - Earth (ENU) coordinate frame
    - Multiple ADCP models (Sentinel, Quartermaster, Long Ranger)
    
    Features:
    - Velocity data (UCUR, VCUR, WCUR, ECUR or VEL1-4)
    - Echo intensity (separate for each beam)
    - Correlation magnitude
    - Percent good
    - Temperature, pressure, salinity
    - Heading, pitch, roll
    - Automatic compass correction detection
    """

    parser_name = "Workhorse"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset | list[IMOSDataset]:
        """Parse Workhorse ADCP binary file.
        
        Args:
            filenames: List of file paths (only first file used)
            mode: Data mode - ignored, uses empty string per MATLAB
            
        Returns:
            IMOSDataset with parsed ADCP data. If a matching ``.PD0``/``.WVS``
            wave-data file pair is present alongside the input, returns a list
            ``[current_dataset, wave_dataset]`` (mirrors MATLAB workhorseParse).
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Workhorse parser currently expects exactly one input file")

        source_file = file_list[0]
        
        # Look for a processed current/wave file pair (mirrors workhorseParse:
        # isWaveData = exist('<rad>.PD0') && exist('<rad>.WVS')).
        current_file = source_file.with_suffix('.PD0')
        wave_file = source_file.with_suffix('.WVS')
        is_wave_data = current_file.exists() and wave_file.exists()
        
        # Read binary ensembles (mirrors readWorkhorseEnsembles)
        ensembles = read_workhorse_ensembles(source_file)
        
        if not ensembles or len(ensembles.get('fixedLeader', [])) == 0:
            raise ValueError(f"No valid ensembles found in {source_file}")
        
        # Extract metadata from fixed leader (mirrors Workhorse.load_fixedLeader_metadata)
        meta = WorkhorseMetadata.from_fixed_leader(ensembles['fixedLeader'])
        
        # Determine magnetic declination naming extension
        # Mirrors: no_magnetic_corrections = meta.compass_correction_applied == 0
        no_magnetic_corrections = meta.compass_correction_applied == 0
        if no_magnetic_corrections:
            magdec_name_extension = '_MAG'
            magdec_comment = ''
        else:
            magdec_name_extension = ''
            magdec_comment = (
                f'A compass correction of {meta.compass_correction_applied} '
                'degrees has been applied to the data by a technician using RDI\'s software '
                '(usually to account for magnetic declination).'
            )
        
        # Convert time (mirrors Workhorse.convert_time)
        time = convert_workhorse_time(
            ensembles['variableLeader'],
            meta.instrument_firmware
        )
        
        # Calculate sample interval (mirrors mode(diff(time*24*3600)))
        time_diff = np.diff(time * 24 * 3600)
        if len(time_diff) > 0:
            # Round to avoid float-noise fragmenting the mode, then take mode.
            rounded = np.round(time_diff, 6)
            vals, counts = np.unique(rounded, return_counts=True)
            sample_interval = float(vals[int(np.argmax(counts))])
        else:
            sample_interval = 0.0
        
        # Calculate average interval (mirrors mode(timePerEnsemble))
        tpp_minutes = np.asarray(ensembles['fixedLeader']['tppMinutes'], dtype=np.float64)
        tpp_seconds = np.asarray(ensembles['fixedLeader']['tppSeconds'], dtype=np.float64)
        tpp_hundredths = np.asarray(ensembles['fixedLeader']['tppHundredths'], dtype=np.float64)
        pings_per_ensemble = np.asarray(
            ensembles['fixedLeader']['pingsPerEnsemble'], dtype=np.float64
        )
        time_per_ping = 60.0 * tpp_minutes + tpp_seconds + 0.01 * tpp_hundredths
        time_per_ensemble = pings_per_ensemble * time_per_ping
        if time_per_ensemble.size:
            vals, counts = np.unique(time_per_ensemble, return_counts=True)
            average_interval = float(vals[int(np.argmax(counts))])
        else:
            average_interval = 0.0
        
        # Calculate distance along beams (mirrors Workhorse.cell_cdistance)
        distance = calculate_cell_distances(
            bin1_distance=ensembles['fixedLeader']['bin1Distance'],
            depth_cell_length=ensembles['fixedLeader']['depthCellLength'],
            num_cells=ensembles['fixedLeader']['numCells'],
            beam_face_config=meta.beam_face_config
        )
        
        # Create dataset (mirrors MATLAB struct creation)
        dataset = self._create_dataset(
            source_file=source_file,
            time=time,
            distance=distance,
            ensembles=ensembles,
            meta=meta,
            sample_interval=sample_interval,
            average_interval=average_interval,
            magdec_name_extension=magdec_name_extension,
            magdec_comment=magdec_comment,
        )
        
        if is_wave_data:
            # Read the processed wave ASCII data and build the second dataset
            # (mirrors workhorseParse.m wave section).
            wave_data = read_workhorse_wave_ascii(wave_file)
            wave_dataset = self._create_wave_dataset(
                wave_file=wave_file,
                wave_data=wave_data,
                meta=meta,
                magdec_name_extension=magdec_name_extension,
                magdec_comment=magdec_comment,
            )
            return [dataset, wave_dataset]
        
        return dataset
    
    def _create_dataset(
        self,
        source_file: Path,
        time: np.ndarray,
        distance: np.ndarray,
        ensembles: dict,
        meta: WorkhorseMetadata,
        sample_interval: float,
        average_interval: float,
        magdec_name_extension: str,
        magdec_comment: str,
    ) -> IMOSDataset:
        """Create IMOS-compliant dataset from parsed data.
        
        Mirrors MATLAB workhorseParse.m structure creation logic.
        """
        dataset = IMOSDataset.empty()
        
        # Add TIME dimension (mirrors dimensions{1})
        time_comment = (
            f'Time stamp corresponds to the start of the measurement which lasts '
            f'{average_interval} seconds.'
        )
        dataset.add_dimension('TIME', time)
        
        # Add DIST_ALONG_BEAMS dimension (mirrors dimensions{2})
        distance_comment = (
            'Values correspond to the distance between the instrument\'s transducers and '
            'the centre of each cells. Data is not vertically bin-mapped (no tilt correction applied). '
            'Cells are lying parallel to the beams, at heights above sensor that vary with tilt.'
        )
        dataset.add_dimension('DIST_ALONG_BEAMS', distance)
        
        # Add HEIGHT_ABOVE_SENSOR dimension for ENU coordinates (mirrors dimensions{3})
        if meta.coordinate_frame == 'earth':
            height_comment = (
                'Values correspond to the distance between the instrument\'s transducers and '
                'the centre of each cells. Data has been vertically bin-mapped using tilt information '
                'so that the cells have consistent heights above sensor in time.'
            )
            dataset.add_dimension('HEIGHT_ABOVE_SENSOR', distance)
        
        # Add scaffold variables (TIMESERIES, LATITUDE, LONGITUDE, NOMINAL_DEPTH)
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
        
        # Apply missing value filter (mirrors fill_missing_with_nan)
        apply_missing_value_filter(ensembles)
        
        # Apply bad orientation filter (mirrors bad_orientation check)
        apply_bad_orientation_filter(ensembles, meta)
        
        # Add velocity variables (mirrors vars2d_vel creation)
        create_velocity_variables(
            dataset=dataset,
            ensembles=ensembles,
            meta=meta,
            magdec_name_extension=magdec_name_extension,
            magdec_comment=magdec_comment,
        )
        
        # Add beam variables (mirrors vars2d_beam creation)
        create_beam_variables(
            dataset=dataset,
            ensembles=ensembles,
            meta=meta,
        )
        
        # Add timeseries variables (mirrors vars1d creation)
        create_timeseries_variables(
            dataset=dataset,
            ensembles=ensembles,
            meta=meta,
        )
        
        # Set global attributes
        dataset.set_attrs({
            'toolbox_input_file': str(source_file),
            'featureType': '',  # Empty per MATLAB: sample_data.meta.featureType = ''
            'instrument_make': 'Teledyne RDI',
            'instrument_model': meta.instrument_model,
            'instrument_serial_no': meta.instrument_serial_no,
            'instrument_firmware': meta.instrument_firmware,
            'beam_angle': meta.beam_angle,
            'beam_pattern': meta.beam_pattern,
            'beam_config': meta.beam_config,
            'beam_face_config': meta.beam_face_config,
            'coordinate_frame': meta.coordinate_frame,
            'compass_correction_applied': meta.compass_correction_applied,
            'instrument_sample_interval': sample_interval,
            'instrument_average_interval': average_interval,
            'parser': self.parser_name,
            'source_format': 'binary_pd0',
        })
        
        # Add dimension comments as attributes (stored on coordinate variables)
        if 'TIME' in dataset.dataset.coords:
            dataset.dataset.coords['TIME'].attrs['comment'] = time_comment
            dataset.dataset.coords['TIME'].attrs['seconds_to_middle_of_measurement'] = average_interval / 2
        
        if 'DIST_ALONG_BEAMS' in dataset.dataset.coords:
            dataset.dataset.coords['DIST_ALONG_BEAMS'].attrs['comment'] = distance_comment
        
        if meta.coordinate_frame == 'earth':
            if 'HEIGHT_ABOVE_SENSOR' in dataset.dataset.coords:
                dataset.dataset.coords['HEIGHT_ABOVE_SENSOR'].attrs['comment'] = height_comment
        
        return dataset
    
    def _create_wave_dataset(
        self,
        wave_file: Path,
        wave_data: dict,
        meta: WorkhorseMetadata,
        magdec_name_extension: str,
        magdec_comment: str,
    ) -> IMOSDataset:
        """Build the wave (second) dataset from processed WavesMon ASCII data.
        
        Mirrors the wave section of MATLAB workhorseParse.m.
        """
        import re
        
        param = wave_data['param']
        time = np.asarray(param['time'], dtype=np.float64)
        
        # Average interval parsed from the summary file:
        #   "Each Burst Contains  N Samples, Taken at F Hz." -> avgInterval = N/F
        average_interval = None
        for line in wave_data.get('summary', []):
            m = re.search(
                r'Each Burst Contains\s+([0-9.]+) Samples, Taken at ([0-9.]+) Hz', line
            )
            if m:
                samples = float(m.group(1))
                hz = float(m.group(2))
                if hz != 0:
                    average_interval = samples / hz
                break
        
        # Sample interval (mirrors median(diff(time*24*3600)))
        if time.size > 1:
            sample_interval = float(np.median(np.diff(time * 24 * 3600)))
        else:
            sample_interval = float('nan')
        
        dataset = IMOSDataset.empty()
        
        # --- Dimensions: TIME, FREQUENCY, DIR{ext} ---
        avg_str = average_interval if average_interval is not None else '?'
        time_comment = (
            f'Time stamp corresponds to the start of the measurement which lasts '
            f'{avg_str} seconds.'
        )
        dataset.add_dimension('TIME', time, attrs={'comment': time_comment})
        if average_interval is not None:
            dataset.dataset.coords['TIME'].attrs['seconds_to_middle_of_measurement'] = (
                average_interval / 2
            )
        
        freq = np.asarray(wave_data['Dspec']['freq'], dtype=np.float64)
        dataset.add_dimension('FREQUENCY', freq)
        
        dir_name = f'DIR{magdec_name_extension}'
        direction = np.asarray(wave_data['Dspec']['dir'], dtype=np.float64)
        dir_attrs: dict = {}
        if magdec_name_extension == '':
            # A compass correction was applied
            dir_attrs['compass_correction_applied'] = meta.compass_correction_applied
            dir_attrs['comment'] = magdec_comment
        dataset.add_dimension(dir_name, direction, attrs=dir_attrs)
        
        # --- Scaffold variables ---
        dataset.add_variable('TIMESERIES', data=np.int32(1), dims=[],
                             attrs={'long_name': 'timeSeries index', 'cf_role': 'timeseries_id'})
        dataset.add_variable('LATITUDE', data=np.float64(np.nan), dims=[],
                             attrs={'long_name': 'latitude', 'units': 'degrees_north'})
        dataset.add_variable('LONGITUDE', data=np.float64(np.nan), dims=[],
                             attrs={'long_name': 'longitude', 'units': 'degrees_east'})
        dataset.add_variable('NOMINAL_DEPTH', data=np.float32(np.nan), dims=[],
                             attrs={'long_name': 'nominal depth', 'units': 'meters', 'positive': 'down'})
        
        coords_surface = 'TIME LATITUDE LONGITUDE'
        coords_depth = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        wpdi = f'WPDI{magdec_name_extension}'
        wwpd = f'WWPD{magdec_name_extension}'
        swpd = f'SWPD{magdec_name_extension}'
        vdir = f'VDIR{magdec_name_extension}'
        sswv = f'SSWV{magdec_name_extension}'
        
        # Direction variables that carry the magnetic-declination attributes
        # (only when a correction was actually applied, i.e. ext == '').
        direction_vars = {wpdi, wwpd, swpd, vdir, sswv}
        
        def _attrs(name: str, coordinates: str = coords_surface) -> dict:
            a: dict[str, Any] = {'coordinates': coordinates}
            if magdec_name_extension == '' and name in direction_vars:
                a['compass_correction_applied'] = meta.compass_correction_applied
                a['comment'] = magdec_comment
            return a
        
        # --- Per-time scalar wave parameters (dims = [TIME]) ---
        scalar_vars = [
            ('WSSH', param['Hs']),
            ('WPPE', param['Tp']),
            (wpdi, param['Dp']),
            ('WWSH', param['Hs_W']),
            ('WWPP', param['Tp_W']),
            (wwpd, param['Dp_W']),
            ('SWSH', param['Hs_S']),
            ('SWPP', param['Tp_S']),
            (swpd, param['Dp_S']),
        ]
        for name, data in scalar_vars:
            dataset.add_variable(name, data=np.asarray(data, dtype=np.float64),
                                 dims=['TIME'], attrs=_attrs(name))
        
        # DEPTH (ht is in mm -> m), coordinates include NOMINAL_DEPTH
        dataset.add_variable('DEPTH', data=np.asarray(param['ht'], dtype=np.float64) / 1000.0,
                             dims=['TIME'], attrs={'coordinates': coords_depth})
        
        more_scalars = [
            ('WMXH', param['Hmax']),
            ('WMPP', param['Tmax']),
            ('WHTH', param['Hth']),
            ('WPTH', param['Tth']),
            ('WMSH', param['Hmn']),
            ('WPMH', param['Tmn']),
            ('WHTE', param['Hte']),
            ('WPTE', param['Tte']),
            (vdir, param['Dmn']),
        ]
        for name, data in more_scalars:
            dataset.add_variable(name, data=np.asarray(data, dtype=np.float64),
                                 dims=['TIME'], attrs=_attrs(name))
        
        # --- Spectral variables ---
        # Vspec/Pspec/Sspec are in mm/sqrt(Hz): variance = (x/1000)^2
        vspec = np.asarray(wave_data['Vspec']['data'], dtype=np.float64)
        pspec = np.asarray(wave_data['Pspec']['data'], dtype=np.float64)
        sspec = np.asarray(wave_data['Sspec']['data'], dtype=np.float64)
        dataset.add_variable('VDEV', data=(vspec / 1000.0) ** 2,
                             dims=['TIME', 'FREQUENCY'], attrs={'coordinates': coords_surface})
        dataset.add_variable('VDEP', data=(pspec / 1000.0) ** 2,
                             dims=['TIME', 'FREQUENCY'], attrs={'coordinates': coords_surface})
        dataset.add_variable('VDES', data=(sspec / 1000.0) ** 2,
                             dims=['TIME', 'FREQUENCY'], attrs={'coordinates': coords_surface})
        
        # Dspec is in mm^2/Hz/deg: MATLAB applies Dspec.data/1000.^2 == data/1e6
        dspec = np.asarray(wave_data['Dspec']['data'], dtype=np.float64)
        dataset.add_variable(sswv, data=dspec / 1.0e6,
                             dims=['TIME', 'FREQUENCY', dir_name], attrs=_attrs(sswv))
        
        # --- Global attributes (metadata mirrors the current dataset) ---
        dataset.set_attrs({
            'toolbox_input_file': str(wave_file),
            'featureType': '',
            'instrument_make': 'Teledyne RDI',
            'instrument_model': meta.instrument_model,
            'instrument_serial_no': meta.instrument_serial_no,
            'instrument_firmware': meta.instrument_firmware,
            'beam_angle': meta.beam_angle,
            'coordinate_frame': meta.coordinate_frame,
            'compass_correction_applied': meta.compass_correction_applied,
            'instrument_sample_interval': sample_interval,
            'instrument_average_interval': (
                average_interval if average_interval is not None else float('nan')
            ),
            'parser': self.parser_name,
            'source_format': 'wavesmon_ascii',
        })
        
        return dataset
