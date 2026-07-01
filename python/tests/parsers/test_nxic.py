"""
Tests for FSI NXIC parser.

Mirrors MATLAB parser coverage from `Parser/NXICBinaryParse.m`.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from imos_toolbox.parsers.nxic import NXICParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "FSI" / "nxic_ctd"
SCAFFOLD_VARS = ["TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"]
CORE_VARS = ["TEMP", "CNDC", "PRES_REL", "PSAL", "SSPD", "BAT_VOLT"]


def discover_test_files() -> list[str]:
    """Discover all NXIC .ctd test files."""
    if not TEST_DATA_DIR.exists():
        return []
    return sorted(str(path) for path in TEST_DATA_DIR.rglob("*.ctd"))


@pytest.fixture
def parser() -> NXICParser:
    """Create a NXICParser instance."""
    return NXICParser()


@pytest.fixture
def test_files() -> list[str]:
    """Discover all available test files."""
    return discover_test_files()


@pytest.fixture(scope="module")
def sample_dataset():
    files = discover_test_files()
    if not files:
        pytest.skip("No NXIC test files found in data/FSI/nxic_ctd/")
    return NXICParser().parse([files[0]], "timeSeries")


class TestNXICParser:
    """Test suite for NXIC parser."""

    def test_parser_exists(self, parser):
        assert parser is not None
        assert isinstance(parser, NXICParser)
        assert parser.parser_name == "NXIC"

    def test_format_validation(self, parser):
        with pytest.raises(ValueError, match="supports .ctd files only"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_basic_parse(self, sample_dataset):
        assert sample_dataset is not None
        assert "TIME" in sample_dataset.dataset.dims
        assert len(sample_dataset.dataset["TIME"]) > 0
        for var in CORE_VARS:
            assert var in sample_dataset.dataset.data_vars, f"Missing core variable {var}"

    def test_scaffold_variables(self, sample_dataset):
        for var in SCAFFOLD_VARS:
            assert var in sample_dataset.dataset.data_vars, f"Should have {var}"
            assert sample_dataset.dataset[var].dims == (), f"{var} should be scalar"

        assert sample_dataset.dataset["TIMESERIES"].values == 1
        assert np.isnan(sample_dataset.dataset["LATITUDE"].values)
        assert np.isnan(sample_dataset.dataset["LONGITUDE"].values)
        assert np.isnan(sample_dataset.dataset["NOMINAL_DEPTH"].values)

    def test_core_variable_dimensions(self, sample_dataset):
        time_len = int(sample_dataset.dataset.sizes["TIME"])
        for var in CORE_VARS:
            assert sample_dataset.dataset[var].dims == ("TIME",), f"{var} should be on TIME"
            assert sample_dataset.dataset[var].shape == (time_len,), f"{var} length mismatch"

    def test_coordinates_attribute(self, sample_dataset):
        expected_coords = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
        for var in CORE_VARS:
            assert sample_dataset.dataset[var].attrs.get("coordinates") == expected_coords

    def test_metadata(self, sample_dataset):
        attrs = sample_dataset.dataset.attrs
        assert attrs.get("parser") == "NXIC"
        assert attrs.get("featureType") == "timeSeries"
        assert attrs.get("source_format") == "ctd"
        assert attrs.get("instrument_make") in {"Falmouth Scientific Instruments", "Teledyne"}
        assert attrs.get("instrument_model") in {"NXIC CTD", "Citadel CTD"}
        assert str(attrs.get("instrument_serial_no", "")) != ""
        assert "instrument_sample_interval" in attrs

    def test_time_monotonic(self, sample_dataset):
        time = sample_dataset.dataset["TIME"].values.astype(float)
        assert np.all(np.isfinite(time)), "TIME should be finite"
        assert np.all(np.diff(time) >= 0), "TIME should be monotonic non-decreasing"

    def test_smoke_parse_all_real_files(self, parser, test_files):
        if not test_files:
            pytest.skip("No NXIC test files found in data/FSI/nxic_ctd/")

        for filename in test_files:
            dataset = parser.parse([filename], "timeSeries")
            assert "TIME" in dataset.dataset.dims
            assert len(dataset.dataset["TIME"]) > 0
            for var in CORE_VARS:
                assert var in dataset.dataset.data_vars, f"{Path(filename).name}: missing {var}"


class TestNXICSynthetic:
    """Synthetic binary tests for channel decoding and schema assembly."""

    def test_synthetic_ctd_decode(self, tmp_path):
        source_file = tmp_path / "synthetic_nxic.ctd"

        header = bytearray(220)
        header[2:4] = (2200).to_bytes(2, "little")  # serial
        header[5] = 1  # interval operation enabled
        header[28] = 0  # interval hour
        header[29] = 0  # interval minute
        header[30] = 1  # interval second
        header[31] = 0  # record hour
        header[32] = 0  # record minute
        header[33] = 1  # record second
        header[177] = 0  # analog range bits -> int16 ±5V
        header[199] = 41  # sample length
        header[154] = sum(header[:154]) & 0xFF  # header checksum

        def pack_sample(
            unix_seconds: int,
            hundredths: int,
            conductivity_sm: float,
            temp: float,
            pressure: float,
            salinity: float,
            sound_speed: float,
            battery: float,
        ) -> bytes:
            payload = bytearray()
            payload += struct.pack("<I", unix_seconds)
            payload += struct.pack("<B", hundredths)
            payload += struct.pack("<f", conductivity_sm * 10.0)  # stored as mmho/cm
            payload += struct.pack("<f", temp)
            payload += struct.pack("<f", pressure)
            payload += struct.pack("<f", salinity)
            payload += struct.pack("<f", sound_speed)
            payload += struct.pack("<f", battery)
            payload += struct.pack("<hhhh", 0, 0, 0, 0)  # analog channels
            payload += struct.pack("<f", 1.23)  # digital channel
            assert len(payload) == 41
            return bytes(payload)

        base_sec = 1_600_000_000
        samples = b"".join(
            [
                pack_sample(base_sec + 0, 0, 3.1, 12.5, 50.0, 35.0, 1490.0, 2.6),
                pack_sample(base_sec + 1, 50, 3.2, 12.6, 50.1, 35.1, 1490.1, 2.5),
                pack_sample(base_sec + 3, 0, 3.3, 12.7, 50.2, 35.2, 1490.2, 2.4),
            ]
        )
        source_file.write_bytes(bytes(header) + samples)

        dataset = NXICParser().parse([str(source_file)], "timeSeries")

        assert "TIME" in dataset.dataset.dims
        assert dataset.dataset.sizes["TIME"] == 3
        assert np.allclose(dataset.dataset["CNDC"].values, [3.1, 3.2, 3.3], atol=1e-6)
        assert np.allclose(dataset.dataset["TEMP"].values, [12.5, 12.6, 12.7], atol=1e-6)
        assert np.allclose(dataset.dataset["PRES_REL"].values, [50.0, 50.1, 50.2], atol=1e-6)
        assert np.allclose(dataset.dataset["PSAL"].values, [35.0, 35.1, 35.2], atol=1e-6)
        assert np.allclose(dataset.dataset["SSPD"].values, [1490.0, 1490.1, 1490.2], atol=1e-6)
        assert np.allclose(dataset.dataset["BAT_VOLT"].values, [2.6, 2.5, 2.4], atol=1e-6)


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("FSI NXIC CTD Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    files = discover_test_files()
    print(f"Found {len(files)} .ctd files")
    for filename in files:
        file_path = Path(filename)
        print(f"  {file_path.name} ({file_path.stat().st_size / 1024.0:.1f} KB)")
    print(f"{'='*70}\n")
