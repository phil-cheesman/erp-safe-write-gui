# EstShip Uploader

A standalone Windows GUI app that automates daily estimated ship date uploads to SQL Server ERP systems via ODBC. Replaces manual DBeaver/SSMS workflows with a validated, one-click upload process.

## What It Does

1. Load a CSV with sales order line items and estimated ship dates
2. Validate every row against the live database (SO exists, line item exists, item number matches)
3. Show a before/after comparison of date changes
4. Upload in a single transaction with automatic rollback on any mismatch

## CSV Format

```
SO_Number,Line_Item,Item_Number,Est_Ship_Date
   1000001,0000000001,WIDGET-A100,4/20/2026
   1000002,0000000001,GADGET-B200,2026-04-20
   1000003,0000000001,PART-C300,46132
   1000004,0000000001,ASSY-D400,NULL
```

Supported date formats: `M/D/YYYY`, `YYYY-MM-DD`, Excel serial numbers, or `NULL` to clear.

## Setup

### Prerequisites

- Windows with an ODBC DSN configured for your SQL Server database
- The target database must have a `sostrs` table with `csono`, `clineitem`, `citemno`, and `idestship` columns

### Option A: Run the .exe (recommended)

1. Download `EstShipUploader.exe` from [Releases](../../releases)
2. Copy `config/config.example.ini` to `config/config.ini` next to the exe
3. Edit `config.ini` with your DSN and database name
4. Run the exe

### Option B: Run from source

```bash
# Clone and install
git clone https://github.com/phil-cheesman/erp-safe-write-gui.git
cd erp-safe-write-gui
pip install -e .

# Copy and edit config
cp config/config.example.ini config/config.ini
# Edit config/config.ini with your DSN and database name

# Run
python -m estship_uploader
```

### Configuration

Copy `config/config.example.ini` to `config/config.ini` and fill in your values:

```ini
[database]
dsn = MY_DSN

[settings]
database = my_database
```

Credentials can be entered in the GUI or set via environment variables (`ESTSHIP_DB_USER`, `ESTSHIP_DB_PASSWORD`).

## Building the .exe

```bash
pip install -e ".[dev]"
python scripts/build_exe.py
```

Output: `dist/EstShipUploader.exe`

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE)
