"""Shared fixtures — mock pyodbc objects, test configs, sample CSVs."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from estship_uploader.config import AppConfig


# ---------------------------------------------------------------------------
# Mock pyodbc objects
# ---------------------------------------------------------------------------


class MockRow:
    """Simulates a pyodbc Row with index and attribute access."""

    def __init__(self, *values):
        self._values = values

    def __getitem__(self, idx):
        return self._values[idx]

    def __len__(self):
        return len(self._values)


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    """Minimal AppConfig for unit tests."""
    return AppConfig(dsn="TestDSN", database="testdb")


# ---------------------------------------------------------------------------
# Cursor / Connection fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cursor():
    """A mock cursor with common methods."""
    cursor = MagicMock()
    cursor.description = [
        ("col1", None, None, None, None, None, None),
        ("col2", None, None, None, None, None, None),
    ]
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = (0,)
    cursor.rowcount = 0
    cursor.close.return_value = None
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """A mock pyodbc.Connection that returns mock_cursor."""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    conn.execute.return_value = mock_cursor
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# CSV file fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_csv_path(tmp_path):
    """Valid 3-row CSV with M/D/YYYY dates."""
    csv_file = tmp_path / "valid.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,3/6/2026\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n"
        "   2869191,F2D0572DCA,01-04579/2,3/11/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_bad_dates(tmp_path):
    """CSV with unparseable date."""
    csv_file = tmp_path / "bad_dates.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,not-a-date\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_missing_cols(tmp_path):
    """Wrong column headers."""
    csv_file = tmp_path / "wrong_cols.csv"
    csv_file.write_text(
        "OrderNum,LineNum,ItemNum,ShipDate\n"
        "SO-001,L1,ITEM-1,2026-04-15\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_blank_rows(tmp_path):
    """Valid rows interspersed with blank rows."""
    csv_file = tmp_path / "blanks.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,3/6/2026\n"
        ",,,\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n"
        "  ,  ,  ,  \n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_iso_dates(tmp_path):
    """CSV with YYYY-MM-DD dates."""
    csv_file = tmp_path / "iso_dates.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,2026-03-06\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,2026-04-20\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_missing_fields(tmp_path):
    """CSV with a row missing required field."""
    csv_file = tmp_path / "missing_field.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,,01-0014,3/6/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_header_only(tmp_path):
    """CSV with only headers, no data rows."""
    csv_file = tmp_path / "header_only.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_excel_serial(tmp_path):
    """CSV with Excel serial date numbers."""
    csv_file = tmp_path / "excel_serial.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,46112\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,46157\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_null_date(tmp_path):
    """CSV with NULL date to clear an existing date."""
    csv_file = tmp_path / "null_date.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,NULL\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_duplicate_same_date(tmp_path):
    """CSV with duplicate SO/Line pair, same date."""
    csv_file = tmp_path / "dup_same.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,3/6/2026\n"
        "   2873157,a7EF0MVPRF,01-0014,3/6/2026\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_duplicate_diff_dates(tmp_path):
    """CSV with duplicate SO/Line pair, different dates."""
    csv_file = tmp_path / "dup_diff.csv"
    csv_file.write_text(
        "SO_Number,Line_Item,Item_Number,Est_Ship_Date\n"
        "   2873157,a7EF0MVPRF,01-0014,3/6/2026\n"
        "   2873157,a7EF0MVPRF,01-0014,4/15/2026\n"
        "   2844846,a7B90XEBT8,FNR316118-M50,4/20/2026\n",
        encoding="utf-8",
    )
    return str(csv_file)


# ---------------------------------------------------------------------------
# Item class CSV fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_itemclass_csv(tmp_path):
    """Valid 3-row item class CSV."""
    csv_file = tmp_path / "valid_ic.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100,A\n"
        "GADGET-B200,MTO\n"
        "PART-C300,D\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_blank_buyer(tmp_path):
    """Item class CSV with blank cbuyer (wipe)."""
    csv_file = tmp_path / "blank_buyer.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100,\n"
        "GADGET-B200,A\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_non_approved(tmp_path):
    """Item class CSV with non-approved cbuyer value."""
    csv_file = tmp_path / "non_approved.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100,STOCK\n"
        "GADGET-B200,JBK\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_wrong_headers(tmp_path):
    """Item class CSV with wrong headers."""
    csv_file = tmp_path / "wrong_hdr.csv"
    csv_file.write_text(
        "item,class\n"
        "WIDGET-A100,A\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_dup_same(tmp_path):
    """Item class CSV with duplicate citemno, same value."""
    csv_file = tmp_path / "dup_same_ic.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100,A\n"
        "WIDGET-A100,A\n"
        "GADGET-B200,B\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_dup_diff(tmp_path):
    """Item class CSV with duplicate citemno, conflicting values."""
    csv_file = tmp_path / "dup_diff_ic.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100,A\n"
        "WIDGET-A100,B\n"
        "GADGET-B200,D\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_padded(tmp_path):
    """Item class CSV with CHAR-padded whitespace (like DB export)."""
    csv_file = tmp_path / "padded_ic.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        "WIDGET-A100            ,A         \n"
        "GADGET-B200            ,MTO       \n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_itemclass_csv_missing_item(tmp_path):
    """Item class CSV with missing citemno."""
    csv_file = tmp_path / "missing_item.csv"
    csv_file.write_text(
        "citemno,cbuyer\n"
        ",A\n"
        "GADGET-B200,B\n",
        encoding="utf-8",
    )
    return str(csv_file)

# ---------------------------------------------------------------------------
# Mfg lead time CSV fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_mfglt_csv(tmp_path):
    """Valid 3-row mfg lead time CSV."""
    csv_file = tmp_path / "valid_lt.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,14\n"
        "GADGET-B200,30\n"
        "PART-C300,7\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_blank_lt(tmp_path):
    """Mfg lead time CSV with blank (NULL) lead time."""
    csv_file = tmp_path / "blank_lt.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,\n"
        "GADGET-B200,30\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_bad_int(tmp_path):
    """Mfg lead time CSV with non-integer value."""
    csv_file = tmp_path / "bad_int.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,abc\n"
        "GADGET-B200,30\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_negative(tmp_path):
    """Mfg lead time CSV with negative value."""
    csv_file = tmp_path / "neg_lt.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,-5\n"
        "GADGET-B200,30\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_large(tmp_path):
    """Mfg lead time CSV with very large value (>365)."""
    csv_file = tmp_path / "large_lt.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,500\n"
        "GADGET-B200,30\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_wrong_headers(tmp_path):
    """Mfg lead time CSV with wrong headers."""
    csv_file = tmp_path / "wrong_hdr_lt.csv"
    csv_file.write_text(
        "item,leadtime\n"
        "WIDGET-A100,14\n",
        encoding="utf-8",
    )
    return str(csv_file)

@pytest.fixture
def sample_mfglt_csv_dup_diff(tmp_path):
    """Mfg lead time CSV with duplicate citemno, different values."""
    csv_file = tmp_path / "dup_diff_lt.csv"
    csv_file.write_text(
        "citemno,nmfgltime\n"
        "WIDGET-A100,14\n"
        "WIDGET-A100,30\n",
        encoding="utf-8",
    )
    return str(csv_file)
