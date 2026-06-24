"""Tests for Nortek Signature/AD2CP parser."""
import pytest
from pathlib import Path
from imos_toolbox.parsers.signature import SignatureParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "Nortek"


class TestSignatureParser:
    def test_parser_exists(self):
        parser = SignatureParser()
        assert parser is not None
        assert parser.parser_name == "Signature"

    def test_format_validation(self):
        parser = SignatureParser()
        with pytest.raises(ValueError, match="supports .ad2cp"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_ad2cp_files_available(self):
        """Check if real .ad2cp test data exists."""
        ad2cp_files = []
        for sig_dir in TEST_DATA_DIR.glob("signature_*"):
            ad2cp_files.extend(sig_dir.rglob("*.ad2cp"))
        print(f"  Found {len(ad2cp_files)} .ad2cp test files")
        if ad2cp_files:
            for f in ad2cp_files[:5]:
                print(f"    {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    def test_parse_real_data(self):
        """Test parsing a real Signature .ad2cp file."""
        ad2cp_files = []
        for sig_dir in TEST_DATA_DIR.glob("signature_*"):
            ad2cp_files.extend(sig_dir.rglob("*.ad2cp"))
        if not ad2cp_files:
            pytest.skip("No .ad2cp files found")
        
        # Pick the smallest file for speed
        smallest = min(ad2cp_files, key=lambda f: f.stat().st_size)
        parser = SignatureParser()
        result = parser.parse([str(smallest)], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        assert dataset is not None
        assert "TIME" in dataset.dataset.dims
        assert dataset.dataset.attrs.get("instrument_make") == "Nortek"
        print(f"  ✓ Parsed: {smallest.name}")
        print(f"    Model: {dataset.dataset.attrs.get('instrument_model')}")
        print(f"    Vars: {list(dataset.dataset.data_vars)[:8]}...")
        print(f"    Dims: {dict(dataset.dataset.sizes)}")


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("Nortek Signature/AD2CP Test Files")
    print(f"{'='*70}")
    ad2cp_files = list(TEST_DATA_DIR.rglob("*.ad2cp"))
    print(f"Found {len(ad2cp_files)} .ad2cp files")
    for f in ad2cp_files[:5]:
        print(f"  {f.parent.name}/{f.name} ({f.stat().st_size/1024:.1f} KB)")
    print(f"{'='*70}\n")
