"""Nortek Signature/AD2CP ADCP parser.

Full port of MATLAB signatureParse.m + readAD2CPBinary.m.
Parses Nortek Signature-series ADCP binary (.ad2cp) files.

Supports:
- Version 3 Burst (Id=0x15) and Average (Id=0x16) data records
- Multiple acquisition modes (returns list of datasets)
- ENU and Beam coordinate systems
- Velocity, amplitude, correlation data
- Sensor data (temperature, pressure, heading, pitch, roll, battery)
- String records (instrument model, magnetic declination)

MATLAB source: Parser/signatureParse.m (880 lines) + Parser/readAD2CPBinary.m (625 lines)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser
from imos_toolbox.parsers.read_ad2cp_binary import read_ad2cp_binary


class SignatureParser(BaseParser):
    """Parser for Nortek Signature/AD2CP binary files (.ad2cp).

    Mirrors MATLAB signatureParse.m. Reads binary AD2CP format, groups records
    by acquisition mode (Burst/Average), and returns one IMOSDataset per mode.
    Only Version 3 data records are supported (matching MATLAB limitation).
    """

    parser_name = "Signature"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset | list[IMOSDataset]:
        """Parse Nortek Signature AD2CP binary file.

        Args:
            filenames: List of file paths (only first used)
            mode: Toolbox mode (ignored; featureType='' per MATLAB)

        Returns:
            IMOSDataset or list[IMOSDataset] (one per acquisition mode)
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Signature parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".ad2cp":
            raise ValueError("Signature parser supports .ad2cp files only")

        # Read binary file
        structures = read_ad2cp_binary(source_file)

        if not structures:
            raise ValueError(f"No valid records found in {source_file}")

        # Extract instrument info from string record (Id=A0)
        instrument_model = ""
        mag_dec = 0.0
        serial_number = ""

        a0_keys = [k for k in structures if k.startswith("IdA0")]
        for a0_key in a0_keys:
            for rec in structures[a0_key]["Data"]:
                string_data = rec.get("String", "")
                if string_data:
                    model = _read_header_key(string_data, "ID", "STR")
                    if model:
                        instrument_model = model
                    decl = _read_header_key(string_data, "GETUSER", "DECL")
                    if decl:
                        try:
                            mag_dec = float(decl)
                        except ValueError:
                            pass
            # Remove from structures after extracting
            del structures[a0_key]
            break

        # Remove unsupported record types (1A altimeter raw, etc.)
        keys_to_remove = [k for k in structures if "Id1A" in k or "Id1C" in k or "Id1D" in k]
        for k in keys_to_remove:
            del structures[k]

        # Only keep Version 3 records (matching MATLAB: only format supported)
        acquisition_modes = [k for k in structures if "Version3" in k and ("Id15" in k or "Id16" in k)]

        if not acquisition_modes:
            # Fall back to any available version
            acquisition_modes = [k for k in structures if "Id15" in k or "Id16" in k]

        if not acquisition_modes:
            raise ValueError(f"No supported burst/average data records found in {source_file}")

        # Get serial number from first record
        first_data = structures[acquisition_modes[0]]["Data"]
        if first_data and "SerialNumber" in first_data[0]:
            serial_number = str(first_data[0]["SerialNumber"])

        # Build datasets
        datasets: list[IMOSDataset] = []
        for acq_mode in acquisition_modes:
            dataset = self._build_dataset(
                source_file=source_file,
                acq_mode_name=acq_mode,
                records=structures[acq_mode]["Data"],
                instrument_model=instrument_model,
                serial_number=serial_number,
                mag_dec=mag_dec,
            )
            if dataset is not None:
                datasets.append(dataset)

        if not datasets:
            raise ValueError(f"Could not build any datasets from {source_file}")

        return datasets if len(datasets) > 1 else datasets[0]

    def _build_dataset(
        self,
        source_file: Path,
        acq_mode_name: str,
        records: list[dict],
        instrument_model: str,
        serial_number: str,
        mag_dec: float,
    ) -> IMOSDataset | None:
        """Build one IMOSDataset from a set of data records.

        Mirrors MATLAB signatureParse.m per-acquisition-mode loop.
        """
        if not records:
            return None

        # Extract common parameters from first record
        first = records[0]
        n_cells = first.get("nCells", 0)
        n_beams = first.get("nBeams", 0)
        coord_sys = first.get("coordSys", 0)
        cell_size = first.get("CellSize", 0) * 0.001  # mm → m
        blank_dist = first.get("Blanking", 0) * 0.001  # mm → m

        if n_cells == 0 or n_beams == 0:
            return None

        n_samples = len(records)

        # Extract time-series data (mirrors MATLAB vertcat + unit conversion)
        time = np.array([r.get("Time", np.nan) for r in records])
        temperature = np.array([r.get("Temperature", 0) for r in records]) * 0.01  # °C
        pressure = np.array([r.get("Pressure", 0) for r in records]) * 0.001  # dBar
        heading = np.array([r.get("Heading", 0) for r in records]) * 0.01  # deg
        pitch = np.array([r.get("Pitch", 0) for r in records]) * 0.01  # deg
        roll = np.array([r.get("Roll", 0) for r in records]) * 0.01  # deg
        speed_of_sound = np.array([r.get("SpeedOfSound", 0) for r in records]) * 0.1  # m/s
        battery = np.array([r.get("BatteryVoltage", 0) for r in records]) * 0.1  # Volt

        # Calculate distance (height above sensor)
        # Mirrors MATLAB: distance = (blanking + cellSize/2):cellSize:(blanking + cellSize/2 + (nCells-1)*cellSize)
        distance = blank_dist + cell_size / 2.0 + np.arange(n_cells) * cell_size

        # Velocity scaling factor
        vel_scaling = first.get("VelocityScaling", -3)
        vel_scale = 10.0 ** vel_scaling  # typically 10^(-3) = 0.001 m/s

        # Extract 2D data (velocity, amplitude, correlation)
        has_velocity = "VelocityData" in first
        has_amplitude = "AmplitudeData" in first
        has_correlation = "CorrelationData" in first

        velocity = None
        amplitude = None
        correlation = None

        if has_velocity:
            velocity = np.zeros((n_samples, n_beams, n_cells), dtype=np.float32)
            for i, r in enumerate(records):
                vd = r.get("VelocityData")
                if vd is not None and vd.shape == (n_beams, n_cells):
                    velocity[i] = vd * vel_scale

        if has_amplitude:
            amplitude = np.zeros((n_samples, n_beams, n_cells), dtype=np.float32)
            for i, r in enumerate(records):
                ad = r.get("AmplitudeData")
                if ad is not None and ad.shape == (n_beams, n_cells):
                    amplitude[i] = ad

        if has_correlation:
            correlation = np.zeros((n_samples, n_beams, n_cells), dtype=np.float32)
            for i, r in enumerate(records):
                cd = r.get("CorrelationData")
                if cd is not None and cd.shape == (n_beams, n_cells):
                    correlation[i] = cd

        # Build dataset
        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", time)

        # Distance dimension based on coordinate system
        # coord_sys: 0=ENU, 1=XYZ, 2=Beam
        if coord_sys == 0:  # ENU
            dist_dim = "HEIGHT_ABOVE_SENSOR"
        else:
            dist_dim = "DIST_ALONG_BEAMS"

        dataset.add_dimension(dist_dim, distance)

        # Scaffold variables
        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        coords_2d = f"TIME LATITUDE LONGITUDE {dist_dim}"
        coords_1d = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"

        # Velocity variables
        # Mirrors MATLAB: ENU uses UCUR/VCUR/WCUR, Beam uses VEL1-4
        if has_velocity and velocity is not None:
            if coord_sys == 0:  # ENU
                mag_ext = "_MAG" if mag_dec == 0 else ""
                vel_names = [f"UCUR{mag_ext}", f"VCUR{mag_ext}", "WCUR"]
                if n_beams > 3:
                    vel_names.append("WCUR_2")
            else:
                vel_names = [f"VEL{i+1}" for i in range(n_beams)]

            for beam_idx, vname in enumerate(vel_names[:n_beams]):
                dataset.add_variable(
                    vname, data=velocity[:, beam_idx, :],
                    dims=["TIME", dist_dim], attrs={"coordinates": coords_2d}
                )

        # Amplitude (backscatter)
        if has_amplitude and amplitude is not None:
            for beam_idx in range(n_beams):
                dataset.add_variable(
                    f"ABSI{beam_idx+1}", data=amplitude[:, beam_idx, :],
                    dims=["TIME", dist_dim], attrs={"coordinates": coords_2d}
                )

        # Correlation
        if has_correlation and correlation is not None:
            for beam_idx in range(n_beams):
                dataset.add_variable(
                    f"CMAG{beam_idx+1}", data=correlation[:, beam_idx, :],
                    dims=["TIME", dist_dim], attrs={"coordinates": coords_2d}
                )

        # 1D sensor variables
        dataset.add_variable("TEMP", data=temperature, dims=["TIME"], attrs={"coordinates": coords_1d})
        dataset.add_variable("PRES_REL", data=pressure, dims=["TIME"], attrs={"coordinates": coords_1d})
        dataset.add_variable("SSPD", data=speed_of_sound, dims=["TIME"], attrs={"coordinates": coords_1d})
        dataset.add_variable("BAT_VOLT", data=battery, dims=["TIME"], attrs={"coordinates": coords_1d})
        dataset.add_variable("PITCH", data=pitch, dims=["TIME"], attrs={"coordinates": coords_1d})
        dataset.add_variable("ROLL", data=roll, dims=["TIME"], attrs={"coordinates": coords_1d})

        heading_name = "HEADING_MAG" if mag_dec == 0 else "HEADING"
        dataset.add_variable(heading_name, data=heading, dims=["TIME"], attrs={"coordinates": coords_1d})

        # Metadata
        sample_interval = float(np.median(np.diff(time) * 24 * 3600)) if len(time) > 1 else float("nan")

        dataset.set_attrs({
            "toolbox_input_file": str(source_file),
            "featureType": "",
            "instrument_make": "Nortek",
            "instrument_model": instrument_model or "Signature",
            "instrument_serial_no": serial_number,
            "instrument_sample_interval": sample_interval,
            "beam_angle": 25.0,
            "nBeams": n_beams,
            "nCells": n_cells,
            "cellSize": cell_size,
            "blankDist": blank_dist,
            "coordinate_system": {0: "ENU", 1: "XYZ", 2: "Beam"}.get(coord_sys, "unknown"),
            "acquisition_mode": acq_mode_name,
            "parser": self.parser_name,
        })

        return dataset


def _read_header_key(header_string: str, section: str, key: str) -> str | None:
    """Extract a value from the Signature string header.

    Mirrors MATLAB read_header_key function. The header is a multi-line
    string with sections like 'ID,STR="Signature500"' or 'GETUSER,DECL=0.0'.
    """
    import re
    pattern = rf'{section}.*?{key}\s*=\s*"?([^"\n,]+)"?'
    match = re.search(pattern, header_string, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
