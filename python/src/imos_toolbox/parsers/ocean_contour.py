"""Nortek OceanContour NetCDF parser.

Full port of MATLAB oceanContourParse.m + Parser/OceanContour/OceanContour.m.
Reads Nortek OceanContour-processed NetCDF files (from Signature instruments).

Supports ENU-coordinate datasets with variable mapping from Nortek naming
conventions to IMOS standard variable names.

MATLAB source: Parser/oceanContourParse.m (41 lines, wrapper) +
               Parser/OceanContour/OceanContour.m (732 lines)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser

# Beam angles by instrument model (mirrors MATLAB OceanContour.beam_angles)
_BEAM_ANGLES = {
    "Signature250": 20.0,
    "Signature500": 25.0,
    "Signature1000": 25.0,
}

# NetCDF variable name → IMOS variable name mapping for ENU coordinates.
# Mirrors MATLAB OceanContour.get_varmap('netcdf', ..., True/False for magdec)
_VARMAP_2D_ENU = {
    "Vel_East": "UCUR",
    "Vel_North": "VCUR",
    "Vel_Up1": "WCUR",
    "Vel_Up2": "WCUR_2",
    "Amp_Beam1": "ABSI1",
    "Amp_Beam2": "ABSI2",
    "Amp_Beam3": "ABSI3",
    "Amp_Beam4": "ABSI4",
    "Cor_Beam1": "CMAG1",
    "Cor_Beam2": "CMAG2",
    "Cor_Beam3": "CMAG3",
    "Cor_Beam4": "CMAG4",
}

_VARMAP_2D_ENU_MAG = {
    "Vel_East": "UCUR_MAG",
    "Vel_North": "VCUR_MAG",
    "Vel_Up1": "WCUR",
    "Vel_Up2": "WCUR_2",
    "Amp_Beam1": "ABSI1",
    "Amp_Beam2": "ABSI2",
    "Amp_Beam3": "ABSI3",
    "Amp_Beam4": "ABSI4",
    "Cor_Beam1": "CMAG1",
    "Cor_Beam2": "CMAG2",
    "Cor_Beam3": "CMAG3",
    "Cor_Beam4": "CMAG4",
}

_VARMAP_1D = {
    "WaterTemperature": "TEMP",
    "Pressure": "PRES_REL",
    "SpeedOfSound": "SSPD",
    "Battery": "BAT_VOLT",
    "Pitch": "PITCH",
    "Roll": "ROLL",
    "Heading": "HEADING",
    "Error": "ERROR",
    "Ambiguity": "AMBIG_VEL",
    "TransmitEnergy": "TRANSMIT_E",
    "NominalCor": "NOMINAL_CORR",
}

_VARMAP_1D_MAG = dict(_VARMAP_1D)
_VARMAP_1D_MAG["Heading"] = "HEADING_MAG"


class OceanContourParser(BaseParser):
    """Parser for Nortek OceanContour-processed NetCDF files.

    Mirrors MATLAB OceanContour.readOceanContourFile. Reads NetCDF files
    exported by Nortek's OceanContour software containing averaged or
    burst velocity profiles from Signature instruments.
    """

    parser_name = "OceanContour"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset | list[IMOSDataset]:
        """Parse OceanContour NetCDF file.

        Args:
            filenames: List of file paths (only first used)
            mode: Toolbox mode (ignored; featureType='' per MATLAB)

        Returns:
            IMOSDataset or list[IMOSDataset] (one per dataset group)
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("OceanContour parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() not in (".nc", ".mat"):
            raise ValueError("OceanContour parser supports .nc and .mat files")

        if source_file.suffix.lower() == ".mat":
            return self._parse_mat(source_file)

        # NetCDF path — OceanContour NetCDF has /Config and /Data groups.
        # Under /Data there are subgroups per acquisition mode (Avg, Burst, etc.)
        try:
            import netCDF4
            root = netCDF4.Dataset(str(source_file), "r")
        except Exception as e:
            raise ValueError(f"Cannot open OceanContour NetCDF: {e}") from e

        try:
            # Read Config attributes (global metadata)
            config_group = root.groups.get("Config")
            if config_group is None:
                raise ValueError("OceanContour file missing 'Config' group")

            file_metadata = {attr: config_group.getncattr(attr) for attr in config_group.ncattrs()}

            data_group = root.groups.get("Data")
            if data_group is None:
                raise ValueError("OceanContour file missing 'Data' group")

            dataset_groups = list(data_group.groups.keys())
            if not dataset_groups:
                raise ValueError("OceanContour 'Data' group has no subgroups")

            results: list[IMOSDataset] = []

            for group_name in dataset_groups:
                grp = data_group.groups[group_name]
                dataset = self._parse_group(
                    source_file, grp, group_name, file_metadata
                )
                if dataset is not None:
                    results.append(dataset)

        finally:
            root.close()

        if len(results) == 1:
            return results[0]
        return results

    def _parse_mat(self, source_file: Path) -> IMOSDataset | list[IMOSDataset]:
        """Parse OceanContour .mat file.
        
        Mirrors MATLAB OceanContour.readOceanContourFile 'mat' branch.
        Reads MATLAB workspace exports from OceanContour software.
        Variable names differ from NetCDF (e.g., VelEast vs Vel_East).
        """
        try:
            from scipy.io import loadmat
        except ImportError:
            raise ImportError(
                "OceanContour .mat support requires scipy. "
                "Install with: uv add scipy"
            )
        
        matdata = loadmat(str(source_file), squeeze_me=True)
        
        if "Config" not in matdata:
            raise ValueError("OceanContour .mat file missing 'Config' field")
        
        file_metadata = matdata["Config"]
        if hasattr(file_metadata, "dtype") and file_metadata.dtype.names:
            # Convert structured array to dict
            config = {name: file_metadata[name].item() for name in file_metadata.dtype.names}
        else:
            config = {}
        
        # Find data groups (fieldnames ending in '_Data')
        dataset_groups = [k for k in matdata if k.endswith("_Data") and not k.startswith("_")]
        
        if not dataset_groups:
            raise ValueError("OceanContour .mat file has no data groups")
        
        results: list[IMOSDataset] = []
        
        # .mat variable map (mirrors MATLAB OceanContour.get_varmap 'mat' branch)
        mat_varmap_2d = {
            "VelEast": "UCUR",
            "VelNorth": "VCUR",
            "VelUp1": "WCUR",
            "VelUp2": "WCUR_2",
            "AmpBeam1": "ABSI1",
            "AmpBeam2": "ABSI2",
            "AmpBeam3": "ABSI3",
            "AmpBeam4": "ABSI4",
            "CorBeam1": "CMAG1",
            "CorBeam2": "CMAG2",
            "CorBeam3": "CMAG3",
            "CorBeam4": "CMAG4",
        }
        mat_varmap_1d = {
            "WaterTemperature": "TEMP",
            "Pressure": "PRES_REL",
            "SpeedOfSound": "SSPD",
            "Battery": "BAT_VOLT",
            "Pitch": "PITCH",
            "Roll": "ROLL",
            "Heading": "HEADING",
        }
        
        for group_key in dataset_groups:
            group_name = group_key.split("_Data")[0]
            group_data = matdata[group_key]
            
            if not hasattr(group_data, "dtype") or group_data.dtype.names is None:
                continue
            
            # Extract data fields
            fields = {name: np.asarray(group_data[name].item()) for name in group_data.dtype.names}
            
            time = fields.get("MatlabTimeStamp")
            height = fields.get("Range")
            if time is None or height is None:
                continue
            
            time = time.ravel()
            height = height.ravel()
            
            dataset = IMOSDataset.empty()
            dataset.add_dimension("TIME", time)
            dataset.add_dimension("HEIGHT_ABOVE_SENSOR", height)
            dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
            dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
            dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
            dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])
            
            coords_2d = "TIME LATITUDE LONGITUDE HEIGHT_ABOVE_SENSOR"
            coords_1d = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
            
            for mat_name, imos_name in mat_varmap_2d.items():
                if mat_name in fields:
                    data = fields[mat_name]
                    if data.ndim == 2:
                        if data.shape[0] == len(height) and data.shape[1] == len(time):
                            data = data.T
                    dataset.add_variable(imos_name, data=data, dims=["TIME", "HEIGHT_ABOVE_SENSOR"],
                                         attrs={"coordinates": coords_2d})
            
            for mat_name, imos_name in mat_varmap_1d.items():
                if mat_name in fields:
                    data = fields[mat_name].ravel()
                    dataset.add_variable(imos_name, data=data, dims=["TIME"],
                                         attrs={"coordinates": coords_1d})
            
            # Metadata
            instrument_model = str(config.get("Instrument_instrumentName", "Signature"))
            serial = str(config.get("Instrument_serialNumberDoppler", ""))
            beam_angle = float(_BEAM_ANGLES.get(instrument_model, 25.0))
            
            dataset.set_attrs({
                "toolbox_input_file": str(source_file),
                "featureType": "",
                "instrument_make": "Nortek",
                "instrument_model": instrument_model,
                "instrument_serial_no": serial,
                "beam_angle": beam_angle,
                "netcdf_group_name": group_name,
                "parser": self.parser_name,
            })
            
            results.append(dataset)
        
        if not results:
            raise ValueError(f"No valid datasets in .mat file {source_file}")
        
        return results if len(results) > 1 else results[0]

    def _parse_group(
        self,
        source_file: Path,
        grp: Any,
        group_name: str,
        file_metadata: dict[str, Any],
    ) -> IMOSDataset | None:
        """Parse one OceanContour dataset group.

        Mirrors the per-group loop in MATLAB readOceanContourFile.
        """
        meta_midname = group_name[0].lower() + group_name[1:]

        # Resolve metadata fields
        def get_att(key: str) -> Any:
            """Resolve attribute using the OceanContour naming convention."""
            # Try direct attribute first
            if key in file_metadata:
                return file_metadata[key]
            # Try instrument_<midname>_<key> pattern
            instrument_key = f"Instrument_{meta_midname}_{key}"
            if instrument_key in file_metadata:
                return file_metadata[instrument_key]
            return None

        # Determine nBeams
        n_beams_val = get_att("nBeams") or get_att(f"Instrument_{meta_midname}_nBeams")
        if n_beams_val is None:
            n_beams_val = 4
        n_beams = int(n_beams_val)

        # Magnetic declination
        mag_dec = get_att("Instrument_user_decl") or 0.0
        custom_mag = bool(float(mag_dec))

        # Bin mapping detection
        bin_mapping = get_att("DataInfo_transformsAndCorrections_binMapping")
        binmapped = bool(bin_mapping) if bin_mapping is not None else False
        prefix = "BinMap" if binmapped else ""

        # Coordinate system
        coord_key = f"Instrument_{meta_midname}_coordSystem"
        coord_system = file_metadata.get(coord_key, "ENU")
        if coord_system == "XYZ":
            enu_key = "DataInfo_transformsAndCorrections_addENU"
            if file_metadata.get(enu_key):
                coord_system = "ENU"
            else:
                return None  # Non-ENU not supported
        if coord_system != "ENU":
            return None

        # Read variables from group
        def read_var(nc_name: str) -> np.ndarray | None:
            actual = prefix + nc_name if nc_name not in ("MatlabTimeStamp", "CellSize", "SerialNumber") else nc_name
            if actual in grp.variables:
                return np.asarray(grp.variables[actual][:])
            if nc_name in grp.variables:
                return np.asarray(grp.variables[nc_name][:])
            return None

        # TIME — try MatlabTimeStamp first, then 'time' (plain NetCDF timestamp)
        time = read_var("MatlabTimeStamp")
        if time is None:
            # Newer OceanContour files use 'time' variable directly
            if "time" in grp.variables:
                time = np.asarray(grp.variables["time"][:])
            else:
                return None
        if time is None:
            return None

        # HEIGHT_ABOVE_SENSOR (Range)
        range_name = f"{prefix}{group_name}VelocityENU_Range"
        height = read_var(range_name)
        if height is None:
            height = read_var(f"{group_name}VelocityENU_Range")
        if height is None:
            # Try without group prefix
            for vn in grp.variables:
                if "VelocityENU_Range" in vn or "Range" in vn:
                    height = np.asarray(grp.variables[vn][:])
                    break
        if height is None:
            return None

        # Build dataset
        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", time.ravel())
        dataset.add_dimension("HEIGHT_ABOVE_SENSOR", height.ravel())

        # Scaffold variables
        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        coords_1d = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
        coords_2d = "TIME LATITUDE LONGITUDE HEIGHT_ABOVE_SENSOR"

        # Select variable map based on magnetic declination
        varmap_2d = _VARMAP_2D_ENU_MAG if custom_mag else _VARMAP_2D_ENU
        varmap_1d = _VARMAP_1D_MAG if custom_mag else _VARMAP_1D

        # 2D variables (velocity, amplitude, correlation)
        for nc_name, imos_name in varmap_2d.items():
            if n_beams <= 3 and nc_name in ("Vel_Up2", "Amp_Beam4", "Cor_Beam4"):
                continue
            data = read_var(nc_name)
            if data is not None:
                # OceanContour stores 2D data as (cells, time); IMOS needs (time, cells)
                if data.ndim == 2:
                    if data.shape[0] == len(height.ravel()) and data.shape[1] == len(time.ravel()):
                        data = data.T
                dataset.add_variable(
                    imos_name, data=data, dims=["TIME", "HEIGHT_ABOVE_SENSOR"],
                    attrs={"coordinates": coords_2d},
                )

        # 1D variables (sensors)
        for nc_name, imos_name in varmap_1d.items():
            data = read_var(nc_name)
            if data is not None:
                dataset.add_variable(
                    imos_name, data=data.ravel(), dims=["TIME"],
                    attrs={"coordinates": coords_1d},
                )

        # Instrument metadata
        instrument_model = file_metadata.get("Instrument_instrumentName", "Signature")
        beam_angle = _BEAM_ANGLES.get(str(instrument_model), 25.0)

        # Serial number
        serial_data = read_var("SerialNumber")
        serial_no = str(int(serial_data[0])) if serial_data is not None and serial_data.size > 0 else ""

        # Sample interval
        sample_interval_key = f"Instrument_{meta_midname}_measurementInterval"
        sample_interval = file_metadata.get(sample_interval_key, float("nan"))

        # Mode-specific interval
        avg_interval_key = f"Instrument_{meta_midname}_averagingInterval"
        avg_interval = file_metadata.get(avg_interval_key)

        attrs: dict[str, Any] = {
            "toolbox_input_file": str(source_file),
            "featureType": "",
            "instrument_make": "Nortek",
            "instrument_model": str(instrument_model),
            "instrument_serial_no": serial_no,
            "beam_angle": float(beam_angle),
            "coordinate_system": coord_system,
            "nBeams": n_beams,
            "instrument_sample_interval": float(sample_interval) if sample_interval else float("nan"),
            "netcdf_group_name": group_name,
            "parser": self.parser_name,
        }
        if avg_interval is not None:
            attrs["instrument_avg_interval"] = float(avg_interval)

        dataset.set_attrs(attrs)
        return dataset
