"""
Tests for JFE Infinity SD Logger parser.

Mirrors MATLAB parser coverage from `Parser/infinitySDLoggerParse.m`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from imos_toolbox.parsers.infinity_sd import InfinitySDParser, _fix_repeated_times_jfe

TEST_DATA_DIR = Path(__file__).parent / "data" / "JFE" / "v000"
SCAFFOLD_VARS = ["TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"]
CORE_VARS = ["TEMP", "CPHL", "TURBF", "BAT_VOLT"]


def discover_test_files() -> list[str]:
    """Discover all Infinity SD test files (.csv)."""
    if not TEST_DATA_DIR.exists():
        return []
    return sorted(str(path) for path in TEST_DATA_DIR.rglob("*.csv"))


@pytest.fixture
def parser() -> InfinitySDParser:
    return InfinitySDParser()


@pytest.fixture
def test_files() -> list[str]:
    return discover_test_files()


@pytest.fixture(scope="module")
def sample_dataset():
    files = discover_test_files()
    if not files:
        pytest.skip("No Infinity SD test files found in data/JFE/v000/")
    return InfinitySDParser().parse([files[0]], "timeSeries")


class TestInfinitySDParser:
    """Test suite for Infinity SD parser."""

    def test_parser_exists(self, parser):
        assert parser is not None
        assert isinstance(parser, InfinitySDParser)
        assert parser.parser_name == "InfinitySD"

    def test_format_validation(self, parser):
        with pytest.raises(ValueError, match="supports .csv files only"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_basic_parse(self, sample_dataset):
        assert sample_dataset is not None
        assert "TIME" in sample_dataset.dataset.dims
        assert len(sample_dataset.dataset["TIME"]) > 0
        for var in CORE_VARS:
            assert var in sample_dataset.dataset.data_vars, f"Missing core variable {var}"

    def test_scaffold_variables(self, sample_dataset):
        for var in SCAFFOLD_VARS:
            assert var in sample_dataset.dataset.data_vars
            assert sample_dataset.dataset[var].dims == (), f"{var} should be scalar"

        assert sample_dataset.dataset["TIMESERIES"].values == 1
        assert np.isnan(sample_dataset.dataset["LATITUDE"].values)
        assert np.isnan(sample_dataset.dataset["LONGITUDE"].values)
        assert np.isnan(sample_dataset.dataset["NOMINAL_DEPTH"].values)

    def test_coordinates_attribute(self, sample_dataset):
        expected = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
        for var in CORE_VARS:
            assert sample_dataset.dataset[var].dims == ("TIME",)
            assert sample_dataset.dataset[var].attrs.get("coordinates") == expected

    def test_metadata(self, sample_dataset):
        attrs = sample_dataset.dataset.attrs
        assert attrs.get("parser") == "InfinitySD"
        assert attrs.get("source_format") == "csv"
        assert attrs.get("featureType") == "timeSeries"
        assert attrs.get("instrument_make") == "JFE"
        assert str(attrs.get("instrument_model", "")) != ""
        assert str(attrs.get("instrument_serial_no", "")) != ""
        assert "instrument_sample_interval" in attrs

    def test_cphl_turbf_comments(self, sample_dataset):
        assert "comment" in sample_dataset.dataset["CPHL"].attrs
        assert "comment" in sample_dataset.dataset["TURBF"].attrs
        assert "chlorophyll" in sample_dataset.dataset["CPHL"].attrs["comment"].lower()
        assert "turbidity" in sample_dataset.dataset["TURBF"].attrs["comment"].lower()

    def test_smoke_parse_all_files(self, parser, test_files):
        if not test_files:
            pytest.skip("No Infinity SD test files found in data/JFE/v000/")

        for filename in test_files:
            dataset = parser.parse([filename], "timeSeries")
            assert "TIME" in dataset.dataset.dims
            assert len(dataset.dataset["TIME"]) > 0
            assert np.all(np.diff(dataset.dataset["TIME"].values.astype(float)) >= 0)

    def test_repeated_time_correction(self, parser, test_files):
        microsec_file = next(
            (path for path in test_files if "microsec" in Path(path).name.lower()),
            None,
        )
        if microsec_file is None:
            pytest.skip("No microsecond/repeated-time Infinity SD fixture found")

        dataset = parser.parse([microsec_file], "timeSeries")
        time = dataset.dataset["TIME"].values.astype(float)
        dt = np.diff(time) * 24.0 * 3600.0

        assert np.all(dt > 0), "Repeated timestamps should be corrected to strictly increasing"
        assert np.isclose(np.median(dt), 0.1, atol=0.02), "Expected ~0.1s corrected sampling"


def test_fix_repeated_times_matlab_example():
    """Exact parity with MATLAB ``Util/fixRepeatedTimesJFE.m`` worked example.

    Reproduces the assertions documented in the MATLAB function header, which
    exercise the truncated first burst (tail-aligned), interior bursts, and the
    truncated last burst (head-aligned).
    """
    sbase = 1.0 / 86400.0
    time = np.concatenate([
        np.full(3, 1 * sbase),
        np.full(10, 2 * sbase),
        np.full(10, 15 * 60 * sbase),
        np.full(5, 16 * 60 * sbase),
    ])

    newtime = _fix_repeated_times_jfe(time)

    def as_mm_ss_fff(day_value: float) -> str:
        milliseconds = round(day_value * 86400.0 * 1000.0)
        minutes, remainder = divmod(milliseconds, 60000)
        return f"{minutes:02d}:{remainder / 1000.0:06.3f}"

    # 1-indexed positions from the MATLAB header comment.
    expected = {
        1: "00:01.700",
        3: "00:01.900",
        4: "00:02.000",
        13: "00:02.900",
        14: "15:00.000",
        15: "15:00.100",
        23: "15:00.900",
        24: "16:00.000",
        28: "16:00.400",
    }
    for position, text in expected.items():
        assert as_mm_ss_fff(newtime[position - 1]) == text

    assert np.all(np.diff(newtime) > 0)


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("JFE Infinity SD Logger Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    files = discover_test_files()
    if not files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.csv")
    else:
        print(f"\nFound {len(files)} test files:")
        for filename in files:
            file_path = Path(filename)
            print(f"  {file_path.name} ({file_path.stat().st_size} bytes)")
    print(f"{'='*70}\n")
