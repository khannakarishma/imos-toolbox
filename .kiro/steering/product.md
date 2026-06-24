# IMOS Toolbox - Product Overview

The IMOS Toolbox converts oceanographic instrument files into quality-controlled, IMOS-compliant NetCDF files.

## Purpose

- Process data from instruments deployed on moorings (time series) or during casts (profiles)
- Apply automatic and manual quality control (QC) procedures
- Generate standardized NetCDF outputs meeting IMOS conventions
- Ingest deployment metadata from databases, CSV files, or manual GUI entry

## Dual Implementation

**MATLAB (Legacy)**
- Current production system
- Requires MATLAB R2018b or newer for library usage
- Stand-alone application uses MATLAB Component Runtime (MCR v95)
- GUI and batch processing modes

**Python (Active Port)**
- Modern replacement in development under `python/` directory
- Uses Python 3.14 with `uv` package manager
- Dash-based web UI replacing MATLAB GUI
- See `python/docs/ROADMAP.md` for migration progress

## License

GNU GPLv3 - maintained by ANMN (Australian National Mooring Network) and AODN (Australian Ocean Data Network)
