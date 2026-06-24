"""Nortek Aquadopp Profiler ADCP parser implementation.

Parses binary files from Nortek Aquadopp Profiler instruments (.prf files).
Mirrors MATLAB aquadoppProfilerParse.m as an exact functional port.

Does not yet fully validate HR Aquadopp profilers, but reads HR (Id42) and
plain (Id33) profiler velocity records.

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


class AquadoppProfilerParser(BaseParser):
    """Parser for Nortek Aquadopp Profiler ADCP binary files.

    Mirrors MATLAB aquadoppProfilerParse.m.

    Supports:
    - Binary .prf format files
    - Plain (Id33) and HR (Id42) profiler velocity records
    - Beam and ENU coordinate systems
    - Processed (tilt-corrected) velocity data (Id106) when present

    Note: featureType is '' because, while it includes timeSeriesProfile
    velocity data, it also includes timeSeries data such as TEMP.
    """

    parser_name = "Aquadopp Profiler"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        """Parse an Aquadopp Profiler binary file.

        Args:
            filenames: List of file paths (only the first file is used).
            mode: Toolbox data type mode (unused; featureType is '').

        Returns:
            IMOSDataset with parsed ADCP data.
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Aquadopp Profiler parser expects exactly one input file")

        source_file = file_list[0]

        structures = read_paradopp_binary(source_file)
        if not structures:
            raise ValueError(f"No structures found in {source_file}")

        hardware = structures.get("Id5", [])
        head = structures.get("Id4", [])
        user = structures.get("Id0", [])

        if not hardware or not head or not user:
            raise ValueError("Missing required configuration sections (Id0, Id4, Id5)")

        hardware = hardware[0]
        head = head[0]
        user = user[0]

        instrument_type = str(hardware.get("instrumentType", ""))
        is_hr = "HR" in instrument_type

        # Profiler velocity records: Id42 (HR) when present, else Id33.
        if "Id42" in structures:
            profiler_type = "Id42"
            if "HR" not in instrument_type:
                print(
                    f"Warning : {source_file} HR PROFILER instrumentType does "
                    "not match Id42 sector type data"
                )
        else:
            profiler_type = "Id33"
            if "HR" in instrument_type:
                print(
                    f"Warning : {source_file} AQUADOPP PROFILER instrumentType "
                    "does not match Id33 sector type data"
                )

        velocity_data = structures.get(profiler_type, [])
        if not velocity_data:
            raise ValueError(f"No Aquadopp Profiler velocity data found ({profiler_type})")

        velocity_processed = "Id106" in structures

        # Velocity scaling: 0.1 when bit 5 (1-based) of Mode is set.
        velocity_scaling = 0.1 if (int(user["Mode"]) >> 4) & 1 else 1.0

        distance = self._calculate_distances(user, head)
        cell_size = self._calculate_cell_size(user, head)

        time, sensor_data = self._extract_sensor_data(velocity_data)
        velocity, backscatter = self._extract_velocity_data(velocity_data)

        if velocity_processed:
            processed_data = structures.get("Id106", [])
            velocity, derived_data = self._process_velocity_data(
                processed_data, velocity, time
            )
        else:
            derived_data = {}

        orientation = self._determine_orientation(sensor_data["status"])
        distance, height = self._apply_orientation_to_distance(distance, orientation)

        velocity, backscatter, derived_data = self._filter_bad_orientation(
            velocity, backscatter, derived_data, sensor_data["status"], orientation
        )

        sensor_data = self._convert_sensor_units(sensor_data)
        velocity = self._convert_velocity_units(velocity, velocity_scaling)
        if velocity_processed:
            derived_data = self._convert_derived_units(derived_data)

        instrument_model = "HR Aquadopp Profiler" if is_hr else "Aquadopp Profiler"

        return self._create_dataset(
            source_file=source_file,
            time=time,
            distance=distance,
            height=height,
            cell_size=cell_size,
            velocity=velocity,
            backscatter=backscatter,
            sensor_data=sensor_data,
            derived_data=derived_data,
            user=user,
            head=head,
            hardware=hardware,
            velocity_processed=velocity_processed,
            instrument_model=instrument_model,
        )

    def _frequency_factor(self, freq: int) -> float:
        """Return the frequency-dependent conversion factor.

        Mirrors MATLAB aquadoppProfilerParse.m: 400 kHz -> 0.1195,
        600 kHz -> 0.0797, 1000 kHz -> 0.0478, 2000 kHz -> 0.0239,
        otherwise 0.
        """
        factors = {400: 0.1195, 600: 0.0797, 1000: 0.0478, 2000: 0.0239}
        return factors.get(freq, 0.0)

    def _calculate_cell_size(self, user: dict, head: dict) -> float:
        """Calculate the cell (bin) size in metres."""
        freq = int(head["Frequency"])
        cell_size = int(user["BinLength"])
        factor = self._frequency_factor(freq)
        return (cell_size / 256) * factor * np.cos(25 * np.pi / 180)

    def _calculate_distances(self, user: dict, head: dict) -> np.ndarray:
        """Calculate distance along beams for the centre of each cell."""
        blank_dist = int(user["T2"])
        n_cells = int(user["NBins"])

        cell_size = self._calculate_cell_size(user, head)
        blank_dist = blank_dist * 0.0229 * np.cos(25 * np.pi / 180) - cell_size

        distance = blank_dist + np.arange(n_cells) * cell_size
        distance = distance + cell_size
        return distance

    def _extract_sensor_data(self, velocity_data: list[dict]) -> tuple[np.ndarray, dict]:
        """Extract time and sensor data from velocity records."""
        time = np.array([record["Time"] for record in velocity_data])

        sensor_data = {
            "analn1": np.array([int(r["Analn1"]) for r in velocity_data]),
            "battery": np.array([int(r["Battery"]) for r in velocity_data], dtype=np.float64),
            "sound_speed": np.array([int(r["Analn2"]) for r in velocity_data], dtype=np.float64),
            "heading": np.array([int(r["Heading"]) for r in velocity_data], dtype=np.float64),
            "pitch": np.array([int(r["Pitch"]) for r in velocity_data], dtype=np.float64),
            "roll": np.array([int(r["Roll"]) for r in velocity_data], dtype=np.float64),
            "pressure_msb": np.array([int(r["PressureMSB"]) for r in velocity_data], dtype=np.int64),
            "pressure_lsw": np.array([int(r["PressureLSW"]) for r in velocity_data], dtype=np.int64),
            "temperature": np.array([int(r["Temperature"]) for r in velocity_data], dtype=np.float64),
            "status": np.array([int(r["Status"]) for r in velocity_data], dtype=np.uint8),
        }

        sensor_data["pressure"] = (
            sensor_data["pressure_msb"] * 65536 + sensor_data["pressure_lsw"]
        ).astype(np.float64)

        return time, sensor_data

    def _extract_velocity_data(self, velocity_data: list[dict]) -> tuple[dict, dict]:
        """Extract velocity and backscatter matrices (n_time, n_cells)."""
        velocity = {
            "vel1": np.array([r["Vel1"] for r in velocity_data], dtype=np.float64),
            "vel2": np.array([r["Vel2"] for r in velocity_data], dtype=np.float64),
            "vel3": np.array([r["Vel3"] for r in velocity_data], dtype=np.float64),
        }
        backscatter = {
            "amp1": np.array([r["Amp1"] for r in velocity_data], dtype=np.float64),
            "amp2": np.array([r["Amp2"] for r in velocity_data], dtype=np.float64),
            "amp3": np.array([r["Amp3"] for r in velocity_data], dtype=np.float64),
        }
        return velocity, backscatter

    def _process_velocity_data(
        self,
        processed_data: list[dict],
        velocity: dict,
        time: np.ndarray,
    ) -> tuple[dict, dict]:
        """Replace raw velocity with processed (tilt-corrected) velocity."""
        n_time = len(time)
        n_cells_proc = len(processed_data[0]["Vel1"])

        velocity["vel1"] = np.zeros((n_time, n_cells_proc), dtype=np.float64)
        velocity["vel2"] = np.zeros((n_time, n_cells_proc), dtype=np.float64)
        velocity["vel3"] = np.zeros((n_time, n_cells_proc), dtype=np.float64)

        derived_data = {
            key: np.zeros((n_time, len(processed_data[0][src])), dtype=np.float64)
            for key, src in [
                ("snr1", "Snr1"),
                ("snr2", "Snr2"),
                ("snr3", "Snr3"),
                ("std1", "Std1"),
                ("std2", "Std2"),
                ("std3", "Std3"),
                ("error_code1", "Erc1"),
                ("error_code2", "Erc2"),
                ("error_code3", "Erc3"),
                ("speed", "speed"),
                ("direction", "direction"),
                ("vertical_dist", "verticalDistance"),
                ("profile_error_code", "profileErrorCode"),
                ("qc_flag", "qcFlag"),
            ]
        }

        for record in processed_data:
            idx = np.where(time == record["Time"])[0]
            if len(idx) == 0:
                continue
            i = idx[0]
            velocity["vel1"][i, :] = record["Vel1"]
            velocity["vel2"][i, :] = record["Vel2"]
            velocity["vel3"][i, :] = record["Vel3"]
            derived_data["snr1"][i, :] = record["Snr1"]
            derived_data["snr2"][i, :] = record["Snr2"]
            derived_data["snr3"][i, :] = record["Snr3"]
            derived_data["std1"][i, :] = record["Std1"]
            derived_data["std2"][i, :] = record["Std2"]
            derived_data["std3"][i, :] = record["Std3"]
            derived_data["error_code1"][i, :] = record["Erc1"]
            derived_data["error_code2"][i, :] = record["Erc2"]
            derived_data["error_code3"][i, :] = record["Erc3"]
            derived_data["speed"][i, :] = record["speed"]
            derived_data["direction"][i, :] = record["direction"]
            derived_data["vertical_dist"][i, :] = record["verticalDistance"]
            derived_data["profile_error_code"][i, :] = record["profileErrorCode"]
            derived_data["qc_flag"][i, :] = record["qcFlag"]

        return velocity, derived_data

    def _determine_orientation(self, status: np.ndarray) -> int:
        """Determine ADCP orientation from status bytes (bit 0)."""
        orientations = (status & 0x01).astype(np.uint8)
        vals, counts = np.unique(orientations, return_counts=True)
        return int(vals[int(np.argmax(counts))])

    def _apply_orientation_to_distance(
        self, distance: np.ndarray, orientation: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (distance, height); negate both for downward-looking ADCPs."""
        height = distance.copy()
        if orientation == 1:
            return -distance, -height
        return distance, height

    def _filter_bad_orientation(
        self,
        velocity: dict,
        backscatter: dict,
        derived_data: dict,
        status: np.ndarray,
        expected_orientation: int,
    ) -> tuple[dict, dict, dict]:
        """Set data to NaN where orientation doesn't match the expected value."""
        orientations = (status & 0x01).astype(np.uint8)
        bad_mask = orientations != expected_orientation

        for key in velocity:
            velocity[key][bad_mask, :] = np.nan
        for key in backscatter:
            backscatter[key][bad_mask, :] = np.nan
        for key in derived_data:
            if derived_data[key].ndim == 2:
                derived_data[key][bad_mask, :] = np.nan

        return velocity, backscatter, derived_data

    def _convert_sensor_units(self, sensor_data: dict) -> dict:
        """Convert sensor data to standard units (mirrors MATLAB)."""
        sensor_data["battery"] = sensor_data["battery"] / 10.0
        sensor_data["sound_speed"] = sensor_data["sound_speed"] / 10.0
        sensor_data["heading"] = sensor_data["heading"] / 10.0
        sensor_data["pitch"] = sensor_data["pitch"] / 10.0
        sensor_data["roll"] = sensor_data["roll"] / 10.0
        sensor_data["pressure"] = sensor_data["pressure"] / 1000.0
        sensor_data["temperature"] = sensor_data["temperature"] / 100.0
        return sensor_data

    def _convert_velocity_units(self, velocity: dict, velocity_scaling: float) -> dict:
        """Convert velocity from mm/s to m/s, applying the velocity scaling."""
        for key in velocity:
            velocity[key] = velocity[key] * velocity_scaling / 1000.0
        return velocity

    def _convert_derived_units(self, derived_data: dict) -> dict:
        """Convert derived (processed) data units (mirrors MATLAB)."""
        for key in ("snr1", "snr2", "snr3"):
            derived_data[key][derived_data[key] == 0] = np.nan
            derived_data[key] = 20 * np.log10(derived_data[key])
        for key in ("std1", "std2", "std3"):
            derived_data[key] = derived_data[key] / 1000.0
        derived_data["speed"] = derived_data["speed"] / 1000.0
        derived_data["direction"] = derived_data["direction"] / 100.0
        derived_data["vertical_dist"] = derived_data["vertical_dist"] / 1000.0
        return derived_data

    def _coord_names(self, coord_system: int) -> tuple[str, str, str]:
        """Return (vel1, vel2, vel3) variable names for the coordinate system."""
        if coord_system == 0:  # ENU
            return "UCUR_MAG", "VCUR_MAG", "WCUR"
        if coord_system == 2:  # Beam
            return "VEL1", "VEL2", "VEL3"
        raise ValueError(
            f"{self.parser_name} only supports ENU and Beam coordinate systems"
        )

    def _create_dataset(
        self,
        source_file: Path,
        time: np.ndarray,
        distance: np.ndarray,
        height: np.ndarray,
        cell_size: float,
        velocity: dict,
        backscatter: dict,
        sensor_data: dict,
        derived_data: dict,
        user: dict,
        head: dict,
        hardware: dict,
        velocity_processed: bool,
        instrument_model: str,
    ) -> IMOSDataset:
        """Build the IMOS-compliant dataset (mirrors aquadoppProfilerParse.m)."""
        dataset = IMOSDataset.empty()

        avg_interval = int(user["AvgInterval"])
        time_comment = (
            "Time stamp corresponds to the start of the measurement which lasts "
            f"{avg_interval} seconds."
        )
        dataset.add_dimension("TIME", time, attrs={"comment": time_comment})
        dataset.dataset.coords["TIME"].attrs["seconds_to_middle_of_measurement"] = (
            avg_interval / 2
        )

        dist_comment = (
            "Values correspond to the distance between the instrument's transducers and "
            "the centre of each cells. Nortek instrument data is not vertically bin-mapped "
            "(no tilt correction applied). Cells are lying parallel to the beams, at heights "
            "above sensor that vary with tilt."
        )
        dataset.add_dimension("DIST_ALONG_BEAMS", distance, attrs={"comment": dist_comment})

        if velocity_processed:
            height_comment = (
                "Values correspond to the distance between the instrument's transducers and "
                "the centre of each cells. Data has been vertically bin-mapped using Nortek "
                "Storm software 'Remove tilt effects' procedure. Cells have consistent heights "
                "above sensor in time."
            )
            dataset.add_dimension(
                "HEIGHT_ABOVE_SENSOR", height, attrs={"comment": height_comment}
            )

        # Scaffold variables
        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        vel1_name, vel2_name, vel3_name = self._coord_names(int(user["CoordSystem"]))

        vel_dim = "HEIGHT_ABOVE_SENSOR" if velocity_processed else "DIST_ALONG_BEAMS"
        coords_vel = f"TIME LATITUDE LONGITUDE {vel_dim}"
        coords_diag = "TIME LATITUDE LONGITUDE DIST_ALONG_BEAMS"
        coords_ts = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"

        # MATLAB lists vars as vel2Name, vel1Name, vel3Name (VCUR before UCUR)
        dataset.add_variable(vel2_name, data=velocity["vel2"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})
        dataset.add_variable(vel1_name, data=velocity["vel1"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})
        dataset.add_variable(vel3_name, data=velocity["vel3"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})

        dataset.add_variable("ABSIC1", data=backscatter["amp1"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
        dataset.add_variable("ABSIC2", data=backscatter["amp2"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
        dataset.add_variable("ABSIC3", data=backscatter["amp3"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})

        dataset.add_variable("TEMP", data=sensor_data["temperature"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("PRES_REL", data=sensor_data["pressure"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("BAT_VOLT", data=sensor_data["battery"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("SSPD", data=sensor_data["sound_speed"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("PITCH", data=sensor_data["pitch"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("ROLL", data=sensor_data["roll"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("HEADING_MAG", data=sensor_data["heading"], dims=["TIME"], attrs={"coordinates": coords_ts})

        if velocity_processed:
            dataset.add_variable("SNR1", data=derived_data["snr1"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("SNR2", data=derived_data["snr2"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("SNR3", data=derived_data["snr3"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("NORTEK_ERR1", data=derived_data["error_code1"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("NORTEK_ERR2", data=derived_data["error_code2"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("NORTEK_ERR3", data=derived_data["error_code3"], dims=["TIME", "DIST_ALONG_BEAMS"], attrs={"coordinates": coords_diag})
            dataset.add_variable("CSPD", data=derived_data["speed"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})
            dataset.add_variable("CDIR_MAG", data=derived_data["direction"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})
            dataset.add_variable("NORTEK_PROFILE_ERR", data=derived_data["profile_error_code"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})
            dataset.add_variable("NORTEK_QC", data=derived_data["qc_flag"], dims=["TIME", vel_dim], attrs={"coordinates": coords_vel})

        dataset.set_attrs({
            "toolbox_input_file": str(source_file),
            "featureType": "",
            "binSize": cell_size,
            "instrument_make": "Nortek",
            "instrument_model": instrument_model,
            "instrument_serial_no": hardware["SerialNo"],
            "instrument_firmware": hardware["FWversion"],
            "instrument_sample_interval": float(np.median(np.diff(time * 24 * 3600))),
            "instrument_average_interval": avg_interval,
            "beam_angle": 25.0,
            "beam_to_xyz_transform": head["TransformationMatrix"].tolist(),
            "parser": self.parser_name,
        })

        return dataset
