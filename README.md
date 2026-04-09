# EstShip Uploader

A standalone Windows GUI app that automates daily estimated ship date uploads to SQL Server ERP systems via ODBC. Replaces manual DBeaver/SSMS workflows with a validated, one-click upload process.

## What It Does

A tabbed interface with five uploaders:

**Est Ship Date** — Update estimated ship dates on sales order lines (`sostrs`)
1. Load a CSV with SO number, line item, item number, and new ship date
2. Validate every row against the live database (SO exists, line item exists, item number matches)
3. Upload in a single transaction with automatic rollback on any mismatch

**Item Class** — Update buyer code (`cbuyer`) on items in `iclmas`

**Mfg Lead Time** — Update manufacturing lead time (`nmfgltime`) across all warehouses in `iciwhs`
1. Load a CSV with part numbers and new lead times
2. The app fans out each item to every warehouse that holds it — a single CSV row updates MAIN, HUDSON, NC, etc.
3. A full backup of `iciwhs` is created before each upload; in-transaction validation verifies the exact row count

**Reorder Point** — Update reorder point (`nreordpt`) across all warehouses in `iciwhs`
- Same fan-out and backup pattern as Mfg Lead Time

**Reorder Qty** — Update reorder quantity (`nreordqty`) across all warehouses in `iciwhs`
- Same fan-out and backup pattern as Mfg Lead Time

## CSV Formats

**Est Ship Date:**
```
SO_Number,Line_Item,Item_Number,Est_Ship_Date
   1000001,0000000001,WIDGET-A100,4/20/2026
   1000002,0000000001,GADGET-B200,2026-04-20
   1000003,0000000001,PART-C300,46132
   1000004,0000000001,ASSY-D400,NULL
```

Supported date formats: `M/D/YYYY`, `YYYY-MM-DD`, Excel serial numbers, or `NULL` to clear.

**Mfg Lead Time:**
```
citemno,nmfgltime
WIDGET-A100,14
GADGET-B200,30
PART-C300,0
```

**Item Class:**
```
citemno,cbuyer
WIDGET-A100,A
GADGET-B200,MTO
```

**Reorder Point:**
```
citemno,nreordpt
WIDGET-A100,50
GADGET-B200,100
PART-C300,0
```

**Reorder Qty:**
```
citemno,nreordqty
WIDGET-A100,200
GADGET-B200,500
PART-C300,0
```

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
