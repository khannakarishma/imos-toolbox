"""Tests for FSI NXIC CTD binary parser."""
import pytest
from pathlib import Path
from imos_toolbox.parsers.nxic import NXICParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "FSI" / "nxic_ctd"


class TestNXICParser:
    def test_parser_exists(self):
        parser = NXICParser()
        assert parser is not None
        assert parser.parser_name == "NXIC"

    def test_format_validation(self):
        parser = NXICParser()
        with pytest.raises(ValueError, match="supports .ctd"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_ctd_files_available(self):
        """Check if real NXIC .ctd test data exists."""
        if not TEST_DATA_DIR.exists():
            pytest.skip("No NXIC test data directory")
        ctd_files = list(TEST_DATA_DIR.rglob("*.ctd"))
        assert len(ctd_files) > 0, "Should have .ctd test files"
        print(f"  Found {len(ctd_files)} .ctd test files")
        for f in ctd_files[:5]:
            print(f"    {f.name} ({f.stat().st_size/1024:.1f} KB)")


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("FSI NXIC CTD Test Files")
    print(f"{'='*70}")
    ctd_files = list(TEST_DATA_DIR.rglob("*.ctd")) if TEST_DATA_DIR.exists() else []
    print(f"Found {len(ctd_files)} .ctd files")
    for f in ctd_files:
        print(f"  {f.name} ({f.stat().st_size/1024:.1f} KB)")
    print(f"{'='*70}\n")
