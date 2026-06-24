"""Nortek Aquadopp Velocity (current meter) parser implementation.

Parses binary files from Nortek Aquadopp Velocity instruments (.aqd files).
Mirrors MATLAB aquadoppVelocityParse.m as an exact functional port.

Author: Kiro AI Assistant
Based on MATLAB implementation by Guillaume Galibert
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.parsers.read_paradopp_binary import read_paradopp_binary


class AquadoppVelocityParser(BaseParser):
    """Parser for Nortek Aquadopp Velocity (current meter) binary files.

    Mirrors MATLAB aquadoppVelocityParse.m.

    The Aquadopp current meter records a single cell of velocity per sample
    (Id1), so the output has only a TIME dimension. featureType is set to the
    provided mode (timeSeries or profile).
    """

    parser_name = "Aquadopp Velocity"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        """Parse an Aquadopp Velocity binary file.

        Args:
            filenames: List of file paths (only the first file is used).
            mode: Toolbox data type mode, stored as featureType.

        Returns:
            IMOSDataset with parsed current meter data.
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Aquadopp Velocity parser expects exactly one input file")

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

        # Aquadopp velocity records live in Id1 (current meter velocity data).
        velocity_data = structures.get("Id1", [])
        if not velocity_data:
            raise ValueError("No Aquadopp velocity data found (Id1)")

        cell_size = self._calculate_cell_size(user, head)

        time, sensor_data = self._extract_sensor_data(velocity_data)
        velocity, backscatter = self._extract_velocity_data(velocity_data)

        sensor_data = self._convert_sensor_units(sensor_data)
        velocity = self._convert_velocity_units(velocity)

        return self._create_dataset(
            source_file=source_file,
            time=time,
            cell_size=cell_size,
            velocity=velocity,
            backscatter=backscatter,
            sensor_data=sensor_data,
            user=user,
            head=head,
            hardware=hardware,
            mode=mode,
        )

    def _frequency_factor(self, freq: int) -> float:
        """Return the frequency-dependent conversion factor.

        Mirrors MATLAB aquadoppVelocityParse.m: 2000 kHz -> 0.0239,
        otherwise 0.
        """
        return 0.0239 if freq == 2000 else 0.0

    def _calculate_cell_size(self, user: dict, head: dict) -> float:
        """Calculate the cell (bin) length in metres.

        Distance is not used as a dimension for current meters, but the cell
        length is retained as binSize metadata (mirrors MATLAB).
        """
        freq = int(head["Frequency"])
        cell_length = int(user["BinLength"])
        factor = self._frequency_factor(freq)
        return (cell_length / 256) * factor * np.cos(25 * np.pi / 180)

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
        }

        sensor_data["pressure"] = (
            sensor_data["pressure_msb"] * 65536 + sensor_data["pressure_lsw"]
        ).astype(np.float64)

        return time, sensor_data

    def _extract_velocity_data(self, velocity_data: list[dict]) -> tuple[dict, dict]:
        """Extract per-sample (single cell) velocity and backscatter vectors."""
        velocity = {
            "vel1": np.array([int(r["Vel1"]) for r in velocity_data], dtype=np.float64),
            "vel2": np.array([int(r["Vel2"]) for r in velocity_data], dtype=np.float64),
            "vel3": np.array([int(r["Vel3"]) for r in velocity_data], dtype=np.float64),
        }
        backscatter = {
            "amp1": np.array([int(r["Amp1"]) for r in velocity_data], dtype=np.float64),
            "amp2": np.array([int(r["Amp2"]) for r in velocity_data], dtype=np.float64),
            "amp3": np.array([int(r["Amp3"]) for r in velocity_data], dtype=np.float64),
        }
        return velocity, backscatter

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

    def _convert_velocity_units(self, velocity: dict) -> dict:
        """Convert velocity from mm/s to m/s."""
        for key in velocity:
            velocity[key] = velocity[key] / 1000.0
        return velocity

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
        cell_size: float,
        velocity: dict,
        backscatter: dict,
        sensor_data: dict,
        user: dict,
        head: dict,
        hardware: dict,
        mode: str,
    ) -> IMOSDataset:
        """Build the IMOS-compliant dataset (mirrors aquadoppVelocityParse.m)."""
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

        # Scaffold variables
        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        vel1_name, vel2_name, vel3_name = self._coord_names(int(user["CoordSystem"]))

        # All data variables are 1D over TIME for a current meter.
        coords_ts = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"

        # MATLAB lists vars as vel2Name, vel1Name, vel3Name (VCUR before UCUR)
        dataset.add_variable(vel2_name, data=velocity["vel2"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable(vel1_name, data=velocity["vel1"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable(vel3_name, data=velocity["vel3"], dims=["TIME"], attrs={"coordinates": coords_ts})

        dataset.add_variable("ABSIC1", data=backscatter["amp1"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("ABSIC2", data=backscatter["amp2"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("ABSIC3", data=backscatter["amp3"], dims=["TIME"], attrs={"coordinates": coords_ts})

        dataset.add_variable("TEMP", data=sensor_data["temperature"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("PRES_REL", data=sensor_data["pressure"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("BAT_VOLT", data=sensor_data["battery"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("SSPD", data=sensor_data["sound_speed"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("PITCH", data=sensor_data["pitch"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("ROLL", data=sensor_data["roll"], dims=["TIME"], attrs={"coordinates": coords_ts})
        dataset.add_variable("HEADING_MAG", data=sensor_data["heading"], dims=["TIME"], attrs={"coordinates": coords_ts})

        dataset.set_attrs({
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "binSize": cell_size,
            "instrument_make": "Nortek",
            "instrument_model": "Aquadopp Current Meter",
            "instrument_serial_no": hardware["SerialNo"],
            "instrument_firmware": hardware["FWversion"],
            "instrument_sample_interval": float(np.median(np.diff(time * 24 * 3600))),
            "instrument_average_interval": avg_interval,
            "beam_angle": 45.0,
            "parser": self.parser_name,
        })

        return dataset
