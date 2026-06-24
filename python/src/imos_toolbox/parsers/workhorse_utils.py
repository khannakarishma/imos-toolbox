"""Utility functions for Workhorse ADCP parser.

Mirrors MATLAB +Workhorse namespace functions.

Author: Kiro AI Assistant
Based on MATLAB implementation in Parser/+Workhorse/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from imos_toolbox.model import IMOSDataset


@dataclass
class SensorConfiguration:
    """Sensor availability flags decoded from Fixed Leader bytes 28-29.
    
    Mirrors MATLAB translate_internal_sensor_configuration()
    """
    SpeedOfSound: bool
    Depth: bool
    Heading: bool
    Pitch: bool
    Roll: bool
    Conductivity: bool
    Temperature: bool
    
    @classmethod
    def from_byte(cls, sensor_byte: int) -> SensorConfiguration:
        """Decode sensor configuration from byte value.
        
        Mirrors MATLAB Workhorse.translate_internal_sensor_configuration().
        MATLAB indexes the byte as an MSB-first logical array sconfig(1..8):
            sconfig(2) -> SpeedOfSound  (bit 6, 0x40)
            sconfig(3) -> Depth         (bit 5, 0x20)
            sconfig(4) -> Heading       (bit 4, 0x10)
            sconfig(5) -> Pitch         (bit 3, 0x08)
            sconfig(6) -> Roll          (bit 2, 0x04)
            sconfig(7) -> Conductivity  (bit 1, 0x02)
            sconfig(8) -> Temperature   (bit 0, 0x01)
        
        Args:
            sensor_byte: Sensor configuration byte value
            
        Returns:
            SensorConfiguration with flags
        """
        return cls(
            SpeedOfSound=(sensor_byte & 0x40) != 0,  # bit 6
            Depth=(sensor_byte & 0x20) != 0,         # bit 5
            Heading=(sensor_byte & 0x10) != 0,       # bit 4
            Pitch=(sensor_byte & 0x08) != 0,         # bit 3
            Roll=(sensor_byte & 0x04) != 0,          # bit 2
            Conductivity=(sensor_byte & 0x02) != 0,  # bit 1
            Temperature=(sensor_byte & 0x01) != 0,   # bit 0
        )


@dataclass
class WorkhorseMetadata:
    """ADCP metadata extracted from fixed leader.
    
    Mirrors MATLAB meta structure from Workhorse.load_fixedLeader_metadata
    """
    instrument_make: str
    instrument_model: str
    instrument_serial_no: str
    instrument_firmware: str
    beam_angle: float
    beam_pattern: str
    beam_config: str
    beam_face_config: str
    coordinate_frame: str
    compass_correction_applied: float
    number_of_beams: int
    system_frequency: int
    xmit_voltage_scale: int
    sensors_settings: SensorConfiguration
    sensors_available: SensorConfiguration
    
    @classmethod
    def from_fixed_leader(cls, fixed_leader: dict) -> WorkhorseMetadata:
        """Create metadata from fixed leader data.
        
        Mirrors MATLAB Workhorse.load_fixedLeader_metadata() which uses
        translate_system_configuration / translate_coordinate_transformation
        / translate_internal_sensor_configuration on the mode (most common)
        value of each field.
        """
        def _mode(values: Any) -> int:
            arr = np.asarray(values).ravel()
            vals, counts = np.unique(arr, return_counts=True)
            return int(vals[int(np.argmax(counts))])
        
        # Mode values (a fixed leader should be constant across ensembles)
        system_config = _mode(fixed_leader['systemConfiguration'])
        coord_transform = _mode(fixed_leader['coordTransform'])
        serial_number = _mode(fixed_leader['serialNumber'])
        num_beams = _mode(fixed_leader['numBeams'])
        
        # --- translate_system_configuration ---
        lsb_byte = system_config & 0xFF
        msb_byte = (system_config >> 8) & 0xFF
        
        beam_face_config = 'Up' if (lsb_byte >> 7) & 0x01 else 'Down'
        beam_pattern = 'convex' if (lsb_byte >> 3) & 0x01 else 'concave'
        
        model_id = lsb_byte & 0x07
        model_table = {
            0: (75, 'Long Ranger', 2092719),
            1: (150, 'Quartermaster', 592157),
            2: (300, 'Sentinel or Monitor', 592157),
            3: (600, 'Sentinel or Monitor', 380667),
            4: (1200, 'Sentinel or Monitor', 253765),
            5: (2400, 'DVS', 253765),
        }
        system_freq, model_name, xmit_voltage_scale = model_table.get(
            model_id, (0, 'Unknown', 0)
        )
        
        beam_config_id = (msb_byte >> 4) & 0x0F
        beam_config_table = {
            0x4: '4-BEAM JANUS CONFIG',
            0x5: '5-BEAM JANUS CONFIG DEMOD',
            0xF: '5-BEAM JANUS CONFIG 2 DEMOD',
        }
        beam_config = beam_config_table.get(beam_config_id, 'unknown')
        
        beam_angle_id = msb_byte & 0x03
        beam_angle_table = {0: 15.0, 1: 20.0, 2: 30.0}
        beam_angle = beam_angle_table.get(beam_angle_id, float('nan'))
        
        # MATLAB model name: [model_name ' Workhorse ADCP']
        instrument_model = f'{model_name} Workhorse ADCP'
        
        # Firmware version (cpuFirmwareVersion.cpuFirmwareRevision)
        firmware_ver = _mode(fixed_leader['firmware_version'])
        firmware_rev = _mode(fixed_leader['firmware_revision'])
        instrument_firmware = f'{firmware_ver}.{firmware_rev}'
        
        # --- translate_coordinate_transformation_configuration ---
        # frame = bits 4,3 of the byte -> (byte >> 3) & 0x03
        coord_bits = (coord_transform >> 3) & 0x03
        coordinate_frame = {
            0: 'beam',
            1: 'instrument',
            2: 'ship',
            3: 'earth',
        }.get(coord_bits, 'unknown')
        
        # Compass correction: 0.01 * mode(headingBias) (heading alignment NOT used)
        heading_bias = _mode(fixed_leader['headingBias'])
        compass_correction = 0.01 * heading_bias
        
        # --- translate_internal_sensor_configuration ---
        sensor_source_byte = _mode(fixed_leader['sensorSource'])
        sensor_avail_byte = _mode(fixed_leader['sensorAvail'])
        
        sensors_settings = SensorConfiguration.from_byte(sensor_source_byte)
        sensors_available = SensorConfiguration.from_byte(sensor_avail_byte)
        
        return cls(
            instrument_make='Teledyne RDI',
            instrument_model=instrument_model,
            instrument_serial_no=str(serial_number),
            instrument_firmware=instrument_firmware,
            beam_angle=float(beam_angle),
            beam_pattern=beam_pattern,
            beam_config=beam_config,
            beam_face_config=beam_face_config,
            coordinate_frame=coordinate_frame,
            compass_correction_applied=compass_correction,
            number_of_beams=int(num_beams),
            system_frequency=system_freq,
            xmit_voltage_scale=xmit_voltage_scale,
            sensors_settings=sensors_settings,
            sensors_available=sensors_available,
        )


def convert_workhorse_time(
    variable_leader: dict,
    firmware_version: str
) -> np.ndarray:
    """Convert RTC time to MATLAB datenum format.
    
    Mirrors MATLAB Workhorse.convert_time(): firmware > 8.35 uses the
    Y2K-compliant century/year fields; older firmware uses the 2-digit rtcYear
    with a 1970 century heuristic.
    
    Args:
        variable_leader: Variable leader data with RTC fields
        firmware_version: Firmware version string (e.g. '50.40')
        
    Returns:
        Time array as MATLAB datenum (days since 0000-01-01)
    """
    try:
        fw = float(firmware_version)
    except (TypeError, ValueError):
        fw = 0.0
    
    if fw > 8.35:
        century = np.array(variable_leader['y2kCentury'], dtype=np.int64)
        years_2digit = np.array(variable_leader['y2kYear'], dtype=np.int64)
        full_years = century * 100 + years_2digit
        months = np.array(variable_leader['y2kMonth'], dtype=np.int64)
        days = np.array(variable_leader['y2kDay'], dtype=np.int64)
        hours = np.array(variable_leader['y2kHour'], dtype=np.int64)
        minutes = np.array(variable_leader['y2kMinute'], dtype=np.int64)
        seconds = np.array(variable_leader['y2kSecond'], dtype=np.int64)
        hundredths = np.array(variable_leader['y2kHundredth'], dtype=np.int64)
    else:
        years = np.array(variable_leader['rtcYear'], dtype=np.int64)
        # Mirrors MATLAB: century 2000, or 1900 if first rtcYear > 70
        century_val = 1900 if (years.size and int(years[0]) > 70) else 2000
        full_years = years + century_val
        months = np.array(variable_leader['rtcMonth'], dtype=np.int64)
        days = np.array(variable_leader['rtcDay'], dtype=np.int64)
        hours = np.array(variable_leader['rtcHour'], dtype=np.int64)
        minutes = np.array(variable_leader['rtcMinute'], dtype=np.int64)
        seconds = np.array(variable_leader['rtcSecond'], dtype=np.int64)
        hundredths = np.array(variable_leader['rtcHundredths'], dtype=np.int64)
    
    # Convert to MATLAB datenum
    n = len(full_years)
    time = np.zeros(n, dtype=np.float64)
    for i in range(n):
        try:
            dt = datetime(
                int(full_years[i]),
                int(months[i]),
                int(days[i]),
                int(hours[i]),
                int(minutes[i]),
                int(seconds[i]),
                int(hundredths[i]) * 10000  # hundredths of seconds -> microseconds
            )
            ordinal = dt.toordinal()
            frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
            time[i] = ordinal + 366 + frac  # MATLAB epoch offset
        except (ValueError, OverflowError):
            time[i] = np.nan
    
    return time


def calculate_cell_distances(
    bin1_distance: np.ndarray,
    depth_cell_length: np.ndarray,
    num_cells: np.ndarray,
    beam_face_config: str
) -> np.ndarray:
    """Calculate distance along beams for each depth cell.
    
    Mirrors MATLAB Workhorse.cell_cdistance()
    
    Args:
        bin1_distance: Distance to first bin (cm)
        depth_cell_length: Length of each cell (cm)
        num_cells: Number of cells
        beam_face_config: 'Up' or 'Down'
        
    Returns:
        Distance array in meters (negative for downward looking)
    """
    # Use mode (most common value) - mirrors MATLAB cell_cdistance inputs
    def _mode(values: np.ndarray) -> float:
        arr = np.asarray(values).ravel()
        vals, counts = np.unique(arr, return_counts=True)
        return float(vals[int(np.argmax(counts))])
    
    bin1_dist = _mode(bin1_distance)
    cell_length = _mode(depth_cell_length)
    n_cells = int(_mode(num_cells))
    
    # Calculate distances (mirrors MATLAB formula)
    # distance = 0.01 * (bin1Distance + (0:(numCells-1)) * depthCellLength)
    distances = 0.01 * (bin1_dist + np.arange(n_cells) * cell_length)
    
    # Apply sign based on orientation
    if beam_face_config.lower() == 'down':
        distances = -distances
    
    return distances


def apply_missing_value_filter(ensembles: dict) -> None:
    """Replace missing velocity values (-32768) with NaN.
    
    Mirrors MATLAB fill_missing_with_nan logic in workhorseParse.m
    
    Args:
        ensembles: Ensembles dictionary (modified in place)
    """
    MISSING_VALUE = -32768
    
    # Apply to velocity data
    if 'velocity' in ensembles:
        for key in ['vel1', 'vel2', 'vel3', 'vel4']:
            if key in ensembles['velocity']:
                vel_data = ensembles['velocity'][key]
                for i in range(len(vel_data)):
                    vel_data[i] = np.where(
                        vel_data[i] == MISSING_VALUE,
                        np.nan,
                        vel_data[i]
                    ).astype(np.float32)


def apply_bad_orientation_filter(
    ensembles: dict,
    meta: WorkhorseMetadata,
) -> None:
    """Set bad orientation measurements to NaN.
    
    Mirrors MATLAB bad_orientation filtering logic in workhorseParse.m:
    orientation_bit = strcmpi(meta.adcp_info.beam_face_config,'Up')
    bad_orientation = ensembles.fixedLeader.systemConfiguration(:,1) ~= orientation_bit
    
    Args:
        ensembles: Ensembles dictionary (modified in place)
        meta: ADCP metadata with beam_face_config
    """
    # Determine expected orientation bit (0 for Down, 1 for Up)
    orientation_bit = 1 if meta.beam_face_config.lower() == 'up' else 0
    
    # MATLAB: bad_orientation = systemConfiguration(:,1) ~= orientation_bit
    # systemConfiguration(:,1) is the MSB-first first bit = the UP/DOWN facing
    # bit (bit 7 of the LSB byte), NOT the LSB.
    system_config = np.array(ensembles['fixedLeader']['systemConfiguration'])
    up_facing_bit = (system_config >> 7) & 0x01
    bad_orientation = up_facing_bit != orientation_bit
    
    # Apply NaN to all binned variables (velocity, echo, correlation, percent good)
    # Mirrors: binned_vars = [vel_vars,beam_vars]
    
    # Velocity variables
    if 'velocity' in ensembles:
        for key in ['vel1', 'vel2', 'vel3', 'vel4']:
            if key in ensembles['velocity']:
                vel_data = ensembles['velocity'][key]
                for i, is_bad in enumerate(bad_orientation):
                    if is_bad and i < len(vel_data):
                        vel_data[i][:] = np.nan
    
    # Echo intensity
    if 'echoIntensity' in ensembles:
        for i in range(1, meta.number_of_beams + 1):
            key = f'echo{i}'
            if key in ensembles['echoIntensity']:
                echo_data = ensembles['echoIntensity'][key]
                for j, is_bad in enumerate(bad_orientation):
                    if is_bad and j < len(echo_data):
                        echo_data[j] = np.full(
                            len(echo_data[j]), np.nan, dtype=np.float32
                        )
    
    # Correlation magnitude
    if 'correlationMagnitude' in ensembles:
        for i in range(1, meta.number_of_beams + 1):
            key = f'cor{i}'
            if key in ensembles['correlationMagnitude']:
                cor_data = ensembles['correlationMagnitude'][key]
                for j, is_bad in enumerate(bad_orientation):
                    if is_bad and j < len(cor_data):
                        cor_data[j] = np.full(
                            len(cor_data[j]), np.nan, dtype=np.float32
                        )
    
    # Percent good
    if 'percentGood' in ensembles:
        for i in range(1, meta.number_of_beams + 1):
            key = f'pg{i}'
            if key in ensembles['percentGood']:
                pg_data = ensembles['percentGood'][key]
                for j, is_bad in enumerate(bad_orientation):
                    if is_bad and j < len(pg_data):
                        pg_data[j] = np.full(
                            len(pg_data[j]), np.nan, dtype=np.float32
                        )


def create_velocity_variables(
    dataset: IMOSDataset,
    ensembles: dict,
    meta: WorkhorseMetadata,
    magdec_name_extension: str,
    magdec_comment: str,
) -> None:
    """Create velocity variables in dataset.
    
    Mirrors MATLAB vars2d_vel creation logic with dynamic variable creation.
    Only creates variables based on number of beams.
    
    Args:
        dataset: IMOSDataset to add variables to
        ensembles: Parsed ensemble data
        meta: ADCP metadata
        magdec_name_extension: '_MAG' or ''
        magdec_comment: Comment about magnetic declination correction
    """
    velocity = ensembles['velocity']
    
    # Convert velocity lists to 2D arrays (time x cells)
    vel1 = np.array(velocity['vel1'])
    vel2 = np.array(velocity['vel2'])
    vel3 = np.array(velocity['vel3'])
    vel4 = np.array(velocity['vel4']) if 'vel4' in velocity else None
    
    # Convert from mm/s to m/s (mirrors MATLAB conversion_mappings mms_to_ms)
    vel1 = vel1 / 1000.0
    vel2 = vel2 / 1000.0
    vel3 = vel3 / 1000.0
    if vel4 is not None:
        vel4 = vel4 / 1000.0
    
    # Variable names and coordinates depend on coordinate frame
    if meta.coordinate_frame == 'earth':
        # ENU coordinates
        coords = 'TIME LATITUDE LONGITUDE HEIGHT_ABOVE_SENSOR'
        dims = ['TIME', 'HEIGHT_ABOVE_SENSOR']
        
        # Add UCUR, VCUR, WCUR
        dataset.add_variable(
            name=f'UCUR{magdec_name_extension}',
            data=vel1,
            dims=dims,
            attrs={
                'coordinates': coords,
                'comment': magdec_comment if magdec_comment else None,
            }
        )
        
        dataset.add_variable(
            name=f'VCUR{magdec_name_extension}',
            data=vel2,
            dims=dims,
            attrs={
                'coordinates': coords,
                'comment': magdec_comment if magdec_comment else None,
            }
        )
        
        dataset.add_variable(
            name='WCUR',
            data=vel3,
            dims=dims,
            attrs={'coordinates': coords}
        )
        
        # Only add ECUR if 4-beam ADCP (mirrors import_mappings logic)
        if vel4 is not None and meta.number_of_beams == 4:
            dataset.add_variable(
                name='ECUR',
                data=vel4,
                dims=dims,
                attrs={'coordinates': coords}
            )
        
        # Add derived variables (CSPD, CDIR)
        cspd = np.hypot(vel1, vel2)
        cdir = np.arctan2(vel2, vel1) * 180 / np.pi
        cdir = (90 - cdir) % 360  # Convert to oceanographic convention
        
        dataset.add_variable(
            name='CSPD',
            data=cspd,
            dims=dims,
            attrs={'coordinates': coords}
        )
        
        dataset.add_variable(
            name=f'CDIR{magdec_name_extension}',
            data=cdir,
            dims=dims,
            attrs={
                'coordinates': coords,
                'comment': magdec_comment if magdec_comment else None,
            }
        )
    else:
        # Beam coordinates
        coords = 'TIME LATITUDE LONGITUDE DIST_ALONG_BEAMS'
        dims = ['TIME', 'DIST_ALONG_BEAMS']
        
        dataset.add_variable(
            name='VEL1',
            data=vel1,
            dims=dims,
            attrs={'coordinates': coords}
        )
        
        dataset.add_variable(
            name='VEL2',
            data=vel2,
            dims=dims,
            attrs={'coordinates': coords}
        )
        
        dataset.add_variable(
            name='VEL3',
            data=vel3,
            dims=dims,
            attrs={'coordinates': coords}
        )
        
        # Only add VEL4 if 4-beam ADCP (mirrors import_mappings logic)
        if vel4 is not None and meta.number_of_beams == 4:
            dataset.add_variable(
                name='VEL4',
                data=vel4,
                dims=dims,
                attrs={'coordinates': coords}
            )


def create_beam_variables(
    dataset: IMOSDataset,
    ensembles: dict,
    meta: WorkhorseMetadata,
) -> None:
    """Create beam-related variables (echo intensity, correlation, percent good).
    
    Mirrors MATLAB vars2d_beam creation logic with dynamic beam-based creation.
    Follows import_mappings pattern: ABSIC variables first, then CMAG, then PERG.
    
    Args:
        dataset: IMOSDataset to add variables to
        ensembles: Parsed ensemble data
        meta: ADCP metadata with number_of_beams
    """
    coords = 'TIME LATITUDE LONGITUDE DIST_ALONG_BEAMS'
    dims = ['TIME', 'DIST_ALONG_BEAMS']
    
    # Echo intensity (mirrors ABSIC variables from import_mappings)
    # Only create for beams that exist on this ADCP
    if 'echoIntensity' in ensembles:
        echo = ensembles['echoIntensity']
        for i in range(1, meta.number_of_beams + 1):
            key = f'echo{i}'
            if key in echo:
                data = np.array(echo[key])
                dataset.add_variable(
                    name=f'ABSIC{i}',  # Changed from ABSI to ABSIC to match MATLAB
                    data=data,
                    dims=dims,
                    attrs={'coordinates': coords}
                )
    
    # Correlation magnitude (mirrors CMAG variables from import_mappings)
    if 'correlationMagnitude' in ensembles:
        cor = ensembles['correlationMagnitude']
        for i in range(1, meta.number_of_beams + 1):
            key = f'cor{i}'
            if key in cor:
                data = np.array(cor[key])
                dataset.add_variable(
                    name=f'CMAG{i}',
                    data=data,
                    dims=dims,
                    attrs={'coordinates': coords}
                )
    
    # Percent good (mirrors PERG variables from import_mappings)
    if 'percentGood' in ensembles:
        pg = ensembles['percentGood']
        for i in range(1, meta.number_of_beams + 1):
            key = f'pg{i}'
            if key in pg:
                data = np.array(pg[key])
                dataset.add_variable(
                    name=f'PERG{i}',
                    data=data,
                    dims=dims,
                    attrs={'coordinates': coords}
                )


def create_timeseries_variables(
    dataset: IMOSDataset,
    ensembles: dict,
    meta: WorkhorseMetadata,
) -> None:
    """Create timeseries variables (temperature, pressure, etc.).
    
    Mirrors MATLAB vars1d creation logic with dynamic sensor-based creation.
    Uses sensors_settings to determine which variables to create.
    """
    coords = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
    dims = ['TIME']
    
    var_leader = ensembles['variableLeader']
    sensors = meta.sensors_settings
    
    # Temperature (0.01 degrees C) - only if sensor present
    if sensors.Temperature:
        temp = np.array(var_leader['temperature']) * 0.01
        dataset.add_variable(
            name='TEMP',
            data=temp,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Pressure (decapascals to decibar) - only if sensor present
    # MATLAB conversion_mappings: decapascal_to_decibar = 0.001 * x
    # No atmospheric offset is applied to the DATA in the parser, but MATLAB
    # records the offset that downstream code would apply as an attribute:
    #   xattrs('PRES_REL') = struct('applied_offset', -gsw_P0/10^4) = -10.1325
    if sensors.Depth:
        pres_rel = np.array(var_leader['pressure']) * 0.001
        dataset.add_variable(
            name='PRES_REL',
            data=pres_rel,
            dims=dims,
            attrs={
                'coordinates': coords,
                'applied_offset': np.float32(-10.1325),
            },
        )
    
    # Salinity (ppt) - only if sensor present
    if sensors.Conductivity:
        salinity = np.array(var_leader['salinity'])
        dataset.add_variable(
            name='PSAL',
            data=salinity,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Speed of Sound (m/s) - only if sensor present
    if sensors.SpeedOfSound:
        sound_speed = np.array(var_leader['speedOfSound'])
        dataset.add_variable(
            name='SSPD',
            data=sound_speed,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Heading (0.01 degrees) - only if sensor present
    if sensors.Heading:
        heading = np.array(var_leader['heading']) * 0.01
        # Use magnetic declination extension if no compass correction applied
        heading_name = 'HEADING_MAG' if meta.compass_correction_applied == 0 else 'HEADING'
        dataset.add_variable(
            name=heading_name,
            data=heading,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Pitch (0.01 degrees) - only if sensor present
    if sensors.Pitch:
        pitch = np.array(var_leader['pitch']) * 0.01
        dataset.add_variable(
            name='PITCH',
            data=pitch,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Roll (0.01 degrees) - only if sensor present
    if sensors.Roll:
        roll = np.array(var_leader['roll']) * 0.01
        dataset.add_variable(
            name='ROLL',
            data=roll,
            dims=dims,
            attrs={'coordinates': coords}
        )
    
    # Transmit voltage - ALWAYS present (ADC channel 1)
    # Mirrors readWorkhorseEnsembles ADC masking + workhorseParse fillmissing:
    #   - ADC channels are sampled sequentially (one per ping group). When
    #     pingsPerEnsemble < 8, channels not sampled in an ensemble are NaN.
    #   - TX_VOLT = fillmissing(adcChannel1, 'next') on the raw counts.
    #   - Then convert counts -> volts via xmitcounts_to_volt.
    tx_volt_raw = np.array(var_leader['transmitVoltage'], dtype=np.float64)
    
    n_ens = len(tx_volt_raw)
    pings_arr = np.asarray(ensembles['fixedLeader']['pingsPerEnsemble']).ravel()
    if pings_arr.size:
        vals, counts = np.unique(pings_arr, return_counts=True)
        pings_per_ensemble = int(vals[int(np.argmax(counts))])
    else:
        pings_per_ensemble = 0
    
    n_chan = 8
    if 0 < pings_per_ensemble < n_chan:
        sampled = _adc_channel_sampled_mask(n_ens, pings_per_ensemble, 1, n_chan)
        tx_volt_raw[~sampled] = np.nan
    
    # Fill missing values with the NEXT valid sample (MATLAB fillmissing 'next')
    tx_volt_raw = _fillmissing_next(tx_volt_raw)
    
    # Convert using xmit_voltage_scale (mirrors conversion_mappings)
    # xmitcounts_to_volt = @(x)(1e-6 * xmit_voltage_scale * x)
    tx_volt = 1e-6 * meta.xmit_voltage_scale * tx_volt_raw
    
    volt_comment = (
        'This parameter is actually the transmit voltage (ADC channel 1), which is NOT the same as battery voltage. '
        'The transmit voltage is sampled after a DC/DC converter and as such does not represent the true battery voltage. '
        'It does give a relative illustration of the battery voltage though which means that it will drop as the battery '
        'voltage drops. In addition, The circuit is not calibrated which means that the measurement is noisy and the values '
        'will vary between same frequency WH ADCPs.'
    )
    dataset.add_variable(
        name='TX_VOLT',
        data=tx_volt,
        dims=dims,
        attrs={
            'coordinates': coords,
            'comment': volt_comment,
        }
    )


def _adc_channel_sampled_mask(
    n_ens: int, pings_per_ensemble: int, channel: int, n_chan: int = 8
) -> np.ndarray:
    """Return a boolean mask of ensembles in which an ADC channel was sampled.
    
    Mirrors readWorkhorseEnsembles.m: ADC channels are sampled sequentially,
    one per ping group, cycling 0..7. In ensemble i (0-based) the sampled
    channels are {(i*pingsPerEnsemble + r) mod n_chan : r in 0..pings-1}.
    """
    mask = np.zeros(n_ens, dtype=bool)
    for i in range(n_ens):
        chans = {
            (i * pings_per_ensemble + r) % n_chan
            for r in range(pings_per_ensemble)
        }
        mask[i] = channel in chans
    return mask


def _fillmissing_next(data: np.ndarray) -> np.ndarray:
    """Fill NaN values with the next valid value (MATLAB fillmissing 'next').
    
    Args:
        data: Array with potentially NaN values
        
    Returns:
        Array with NaN values back-filled from the next valid sample. Trailing
        NaN with no following valid value are left as NaN (matching MATLAB).
    """
    result = data.copy()
    next_valid = np.nan
    for i in range(len(result) - 1, -1, -1):
        if np.isnan(result[i]):
            result[i] = next_valid
        else:
            next_valid = result[i]
    return result


def calculate_current_speed_direction(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Calculate current speed and direction from U and V components.
    
    Mirrors MATLAB hypot and azimuth_direction calculations.
    
    Args:
        u: U component (eastward)
        v: V component (northward)
        
    Returns:
        Tuple of (speed, direction) where direction is in oceanographic convention (degrees from north)
    """
    speed = np.hypot(u, v)
    # Convert from math convention (CCW from east) to oceanographic (CW from north)
    direction = (90 - np.arctan2(v, u) * 180 / np.pi) % 360
    return speed, direction
