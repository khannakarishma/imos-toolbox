"""Tests for Echoview CSV export parser."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from imos_toolbox.parsers.echoview import EchoviewParser


@pytest.fixture
def parser() -> EchoviewParser:
    return EchoviewParser()


class TestEchoviewParser:
    """Synthetic tests for Echoview generic CSV parsing."""

    def test_parser_exists(self, parser):
        assert parser is not None
        assert isinstance(parser, EchoviewParser)
        assert parser.parser_name == "Echoview"

    def test_format_validation(self, parser):
        with pytest.raises(ValueError, match="supports .csv files only"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_synthetic_parse(self, parser, tmp_path):
        file_path = _write_synthetic_echoview_csv(tmp_path / "echoview_synthetic.csv")

        dataset = parser.parse([str(file_path)], "timeSeries")
        xds = dataset.dataset

        assert "TIME" in xds.dims
        assert "DEPTH" in xds.dims
        assert int(xds.sizes["TIME"]) == 2
        assert int(xds.sizes["DEPTH"]) == 2

        assert "LATITUDE" in xds.data_vars
        assert "LONGITUDE" in xds.data_vars
        assert "Sv_38" in xds.data_vars
        assert "Sv_pcnt_good_38" in xds.data_vars
        assert xds["Sv_38"].dims == ("TIME", "DEPTH")
        assert xds["Sv_pcnt_good_38"].dims == ("TIME", "DEPTH")

        assert "TIME_QC" in xds.data_vars
        assert "DEPTH_QC" in xds.data_vars
        assert "Sv_38_QC" in xds.data_vars

        sv_qc = xds["Sv_38_QC"].values
        assert sv_qc.shape == (2, 2)
        assert np.array_equal(sv_qc, np.array([[2, 2], [4, 2]], dtype=np.int8))

    def test_singleton_fields(self, parser, tmp_path):
        file_path = _write_synthetic_echoview_csv(tmp_path / "echoview_singletons.csv")
        dataset = parser.parse([str(file_path)], "timeSeries")
        xds = dataset.dataset

        assert "processing_software_version_38" in xds.data_vars
        assert "frequency_38" in xds.data_vars
        assert xds["processing_software_version_38"].dims == ()
        assert xds["frequency_38"].dims == ()
        assert str(xds["processing_software_version_38"].values) == "1.2.3"
        assert float(xds["frequency_38"].values) == 38.0

    def test_metadata(self, parser, tmp_path):
        file_path = _write_synthetic_echoview_csv(tmp_path / "echoview_meta.csv")
        dataset = parser.parse([str(file_path)], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("parser") == "Echoview"
        assert attrs.get("source_format") == "csv"
        assert attrs.get("featureType") == "timeSeries"
        assert attrs.get("instrument_make") == "Simrad"
        assert attrs.get("instrument_model") == "ES60"
        assert attrs.get("EV_csv_file") == "echoview_meta.csv"
        assert attrs.get("site_code") == "SOOP-BA"
        assert attrs.get("level") == 2

    def test_time_datenum_values(self, parser, tmp_path):
        """DT (date + time) fields convert to exact MATLAB datenum values.

        ``datenum(2020,1,1,0,0,0)`` is 737791 in MATLAB; the second timestamp
        (00:10:00) is exactly 10/1440 of a day later.
        """
        file_path = _write_synthetic_echoview_csv(tmp_path / "echoview_time.csv")
        dataset = parser.parse([str(file_path)], "timeSeries")
        xds = dataset.dataset

        time = xds["TIME"].values.astype(float)
        assert time.shape == (2,)
        assert time[0] == pytest.approx(737791.0, abs=1e-9)
        assert time[1] == pytest.approx(737791.0 + 10.0 / 1440.0, abs=1e-9)

        depth = xds["DEPTH"].values.astype(float)
        assert np.array_equal(depth, np.array([10.0, 20.0]))

    def test_missing_time_column_raises(self, parser, tmp_path):
        file_path = tmp_path / "bad.csv"
        file_path.write_text("Layer_depth,Sv_mean\n10,-70\n", encoding="utf-8")
        with pytest.raises(ValueError, match="requires TIME"):
            parser.parse([str(file_path)], "timeSeries")


def _write_synthetic_echoview_csv(path: Path) -> Path:
    rows = [
        [
            "Program_version",
            "Frequency",
            "Date_M",
            "Time_M",
            "Layer_depth",
            "Lat_M",
            "Lon_M",
            "Sv_mean",
            "Pct_good",
        ],
        ["1.2.3", "38", "20200101", "00:00:00.00", "10", "-42.1", "147.2", "-70", "60"],
        ["1.2.3", "38", "20200101", "00:00:00.00", "20", "-42.1", "147.2", "-65", "55"],
        ["1.2.3", "38", "20200101", "00:10:00.00", "10", "-42.2", "147.3", "-60", "45"],
        ["1.2.3", "38", "20200101", "00:10:00.00", "20", "-42.2", "147.3", "-50", "95"],
    ]

    content = "\n".join(",".join(row) for row in rows) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("Echoview Test Files Configuration")
    print(f"{'='*70}")
    print("  No canonical real Echoview CSV fixture is checked in.")
    print("  Parser behavior is validated with synthetic CSV fixtures.")
    print(f"{'='*70}\n")
