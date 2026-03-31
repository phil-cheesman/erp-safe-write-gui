"""Tests for item class CSV parser."""
from estship_uploader.itemclass_csv_parser import parse_itemclass_csv

class TestParseItemclassCsv:
    def test_valid_csv(self, sample_itemclass_csv):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv)
        assert len(rows) == 3
        assert errors == []
        assert rows[0] == ("WIDGET-A100", "A")
        assert rows[1] == ("GADGET-B200", "MTO")

    def test_blank_buyer_maps_to_empty_string(self, sample_itemclass_csv_blank_buyer):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_blank_buyer)
        assert len(rows) == 2
        assert errors == []
        assert rows[0] == ("WIDGET-A100", "")
        assert any("cleared" in w.lower() or "blank" in w.lower() for w in warnings)

    def test_non_approved_value_gives_warning(self, sample_itemclass_csv_non_approved):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_non_approved)
        assert len(rows) == 2
        assert errors == []
        assert len(warnings) >= 1
        assert any("non-approved" in w.lower() or "STOCK" in w for w in warnings)

    def test_wrong_headers(self, sample_itemclass_csv_wrong_headers):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_wrong_headers)
        assert rows == []
        assert len(errors) == 1
        assert "header" in errors[0].lower()

    def test_duplicate_same_value_warning(self, sample_itemclass_csv_dup_same):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_dup_same)
        assert len(rows) == 3
        assert errors == []
        assert any("duplicate" in w.lower() for w in warnings)

    def test_duplicate_different_values_error(self, sample_itemclass_csv_dup_diff):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_dup_diff)
        assert rows == []
        assert len(errors) >= 1
        assert any("conflicting" in e.lower() for e in errors)

    def test_whitespace_stripping(self, sample_itemclass_csv_padded):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_padded)
        assert len(rows) == 2
        assert errors == []
        assert rows[0] == ("WIDGET-A100", "A")
        assert rows[1] == ("GADGET-B200", "MTO")

    def test_case_normalization(self, sample_itemclass_csv):
        """cbuyer values should be uppercased."""
        rows, _, _, _ = parse_itemclass_csv(sample_itemclass_csv)
        for _, buyer in rows:
            assert buyer == buyer.upper()

    def test_missing_citemno_error(self, sample_itemclass_csv_missing_item):
        rows, skipped, errors, warnings = parse_itemclass_csv(sample_itemclass_csv_missing_item)
        assert rows == []
        assert any("missing citemno" in e.lower() for e in errors)

    def test_header_only(self, tmp_path):
        csv_file = tmp_path / "hdr_only.csv"
        csv_file.write_text("citemno,cbuyer\n", encoding="utf-8")
        rows, skipped, errors, warnings = parse_itemclass_csv(str(csv_file))
        assert rows == []
        assert errors == []
