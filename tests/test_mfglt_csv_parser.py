"""Tests for mfg lead time CSV parser."""
from estship_uploader.mfglt_csv_parser import parse_mfglt_csv

class TestParseMfgltCsv:
    def test_valid_csv(self, sample_mfglt_csv):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv)
        assert len(rows) == 3
        assert errors == []
        assert rows[0] == ("WIDGET-A100", 14)
        assert rows[1] == ("GADGET-B200", 30)

    def test_blank_lt_maps_to_none(self, sample_mfglt_csv_blank_lt):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_blank_lt)
        assert len(rows) == 2
        assert errors == []
        assert rows[0] == ("WIDGET-A100", None)
        assert any("cleared" in w.lower() or "null" in w.lower() for w in warnings)

    def test_non_integer_error(self, sample_mfglt_csv_bad_int):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_bad_int)
        assert rows == []
        assert any("abc" in e for e in errors)

    def test_negative_error(self, sample_mfglt_csv_negative):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_negative)
        assert rows == []
        assert any("negative" in e.lower() for e in errors)

    def test_large_value_warning(self, sample_mfglt_csv_large):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_large)
        assert len(rows) == 2
        assert errors == []
        assert any("365" in w for w in warnings)

    def test_wrong_headers(self, sample_mfglt_csv_wrong_headers):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_wrong_headers)
        assert rows == []
        assert len(errors) == 1

    def test_duplicate_diff_error(self, sample_mfglt_csv_dup_diff):
        rows, skipped, errors, warnings = parse_mfglt_csv(sample_mfglt_csv_dup_diff)
        assert rows == []
        assert any("conflicting" in e.lower() for e in errors)

    def test_header_only(self, tmp_path):
        csv_file = tmp_path / "hdr_only.csv"
        csv_file.write_text("citemno,nmfgltime\n", encoding="utf-8")
        rows, skipped, errors, warnings = parse_mfglt_csv(str(csv_file))
        assert rows == []
        assert errors == []
