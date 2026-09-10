# Experiment 01: NeTEx 304MB European Transit Benchmark

## Objective & Background
This benchmark tests the performance, scalability, and memory consumption of the native **PolyXML** engine against standard pure-Python XML binding libraries on massive, highly complex XML data structures.

The test compares:
1. **PolyXML Native Engine** (`CoreXmlParser` / `polyxml` v0.3.0 in Rust)
2. **pyxsdata** (v1.4.0 pure-Python streaming `XmlParser`)
3. **xsdata Predecessor** (v26.2 original pure-Python `XmlParser`)

The test was conducted using:
1. **Schema**: The European Committee for Standardization (CEN) **NeTEx v2.0** Technical Standard ([CEN/TS 16614](https://netex-cen.eu/)), starting from [`NeTEx_publication.xsd`](https://github.com/TransmodelEcosystem/NeTEx/blob/v2.0/xsd/NeTEx_publication.xsd).
2. **Dataset**: A **303.92 MB** national timetable publication dump from the Dutch National Public Transport Data Portal (NDOV Loket / Arriva NL): `NeTEx_ARR_NL_20260909_20260909_1407.xml`.

---

## 3-Way Benchmark Results

| Metric | PolyXML Native Engine (`CoreXmlParser`) | `pyxsdata` (`XmlParser`) | Predecessor `xsdata` (`XmlParser`) | Improvement vs Predecessor (`xsdata`) |
|:---|:---:|:---:|:---:|:---:|
| **Parse Time** | **0.360 seconds** | **70.557 seconds** | **88.004 seconds** | **244.7x FASTER** :rocket: |
| **Throughput** | **845.18 MB/s** | **4.31 MB/s** | **3.45 MB/s** | **~245x Higher Bandwidth** |
| **Peak RAM (RSS)** | **432.89 MB** | **1,703.96 MB** | **1,703.96 MB** | **~75% Less Memory** (~1.27 GB saved) |
| **Data Integrity** | :white_check_mark: Full Extraction | :white_check_mark: Full Extraction | :white_check_mark: Full Extraction | Identical Output |

---

## Test Environment & Hardware Specifications

- **Processor (CPU)**: AMD Ryzen 5 4500 6-Core Processor (12 threads @ 3.6 GHz base)
- **RAM**: 8 GB
- **Operating System**: Linux x86_64 (Kernel 6.6.x)
- **Python Runtime**: CPython 3.12.14
- **Libraries Tested**:
  - `polyxml` v0.3.0 (`quick-xml` 0.37.5, `pyo3` 0.23.5)
  - `pyxsdata` v1.4.0
  - `xsdata` v26.2

---

## Dataset References & Sources

### 1. NeTEx XML Schema Definition (XSD)
- **Upstream Repository**: [TransmodelEcosystem/NeTEx (Release v2.0)](https://github.com/TransmodelEcosystem/NeTEx/tree/v2.0)
- **Primary Schema Entrypoint**: [`xsd/NeTEx_publication.xsd`](https://github.com/TransmodelEcosystem/NeTEx/blob/v2.0/xsd/NeTEx_publication.xsd)
- **Generated Model**: Compiled into `netex_generated.py` (>232,000 lines of standard Python dataclasses, root model `PublicationDelivery`).

### 2. Live Transit Data Source
- **Provider**: NDOV Loket (Netherlands National Public Transport Database)
- **Download URL**: [`https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz`](https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz)
- **File Size**: 12.8 MB compressed (.gz) / 303.92 MB uncompressed (.xml)

---

## Why PolyXML Achieves 245x Performance

1. **Streaming Token Extraction without DOM Allocation**:
   Both `xsdata` and standard `pyxsdata` construct Python element queues and intermediate dictionaries before instantiating target classes. PolyXML uses pure Rust streaming events (`quick-xml`) with SIMD-accelerated delimiter scanning.
2. **Zero-Allocation Byte Conversions**:
   Numerical fields (timestamps, delays, sequence indices, coordinates) are parsed directly from raw UTF-8 byte slices using `lexical-core`, bypassing Python string allocation.
3. **Direct PyO3 Constructor Invocations**:
   Target Python dataclass instances are constructed directly from Rust using PyO3 0.23 `Bound` APIs without intermediate dictionary overhead, drastically cutting garbage collection pressure and reducing peak RSS by ~1.27 GB.

---

## Step-by-Step Reproduction Guide

### 1. Prerequisites & Environment Setup

Install dependencies with `pip` or `uv`:

```bash
pip install -r requirements.txt
# or via uv:
uv pip install -r requirements.txt
```

Contents of `requirements.txt`:
```ini
polyxml>=0.3.0
pyxsdata[cli]>=1.4.0
xsdata[cli]>=26.0
```

---

### 2. Downloading & Extracting the Dataset

Run the included automated helper script:

```bash
./download_data.sh
```

Or perform the steps manually:

```bash
wget https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz
gunzip -k -f NeTEx_ARR_NL_20260909_20260909_1407.xml.gz
```

Verify the file size:
```bash
ls -lh NeTEx_ARR_NL_20260909_20260909_1407.xml
# -rw-r--r-- 1 user user 304M NeTEx_ARR_NL_20260909_20260909_1407.xml
```

---

### 3. Generating Python Dataclass Schemas

You can generate the schema using either **`pyxsdata`** (recommended) or **`xsdata`**.

#### Option A: Automated Script (Recommended)

Generate with `pyxsdata` (default):
```bash
./generate_schema.sh pyxsdata
```

Generate with predecessor `xsdata`:
```bash
./generate_schema.sh xsdata
```

The script automatically clones the NeTEx v2.0 repository, runs code generation, applies the necessary bugfix patch if using `xsdata`, and verifies that `import netex_generated` succeeds in Python.

---

#### Option B: Manual Schema Generation with `pyxsdata`

1. Clone the schema repository:
   ```bash
   git clone --depth 1 --branch v2.0 https://github.com/TransmodelEcosystem/NeTEx.git NeTEx
   ```

2. Run code generation:
   ```bash
   pyxsdata generate NeTEx/xsd/NeTEx_publication.xsd \
       -p netex_generated \
       --structure-style single-package
   ```

3. Validate generated output:
   ```bash
   python3 -c "import netex_generated; print('Loaded successfully!')"
   ```

---

#### Option C: Manual Schema Generation with Predecessor `xsdata`

1. Clone the schema repository:
   ```bash
   git clone --depth 1 --branch v2.0 https://github.com/TransmodelEcosystem/NeTEx.git NeTEx
   ```

2. Run code generation with `xsdata`:
   ```bash
   xsdata generate NeTEx/xsd/NeTEx_publication.xsd \
       -p netex_generated \
       --structure-style single-package
   ```

3. **Important Patch for Upstream `xsdata` (<= 26.2)**:
   In upstream `xsdata`, `Filters.format_string` treats any key named `"default"` as an unquoted code literal rather than a string literal. For XSD elements with string defaults inside dictionary metadata (such as `metadata={"default": "optional"}` in `ClassAttributeInFrameStructure`), `xsdata` generates unquoted code:
   ```python
   mandatory: None | MandatoryEnumeration = field(
       default=None,
       metadata={
           "name": "Mandatory",
           "type": "Element",
           "namespace": "http://www.netex.org.uk/netex",
           "default": optional,  # <-- BUG in xsdata: unquoted token 'optional'
       },
   )
   ```
   This causes `NameError: name 'optional' is not defined` when importing the module.
   
   Apply this one-line fix to quote the string:
   ```bash
   sed -i 's/"default": optional/"default": "optional"/g' netex_generated.py
   ```

4. Validate:
   ```bash
   python3 -c "import netex_generated; print('Loaded successfully!')"
   ```

---

### 4. Running the Benchmark

#### One-Command Runner
```bash
./run_benchmark.sh
```

#### Custom CLI Execution
```bash
# Full 3-way comparative benchmark (PolyXML vs pyxsdata vs xsdata)
python3 run_benchmark.py \
    --xml NeTEx_ARR_NL_20260909_20260909_1407.xml \
    --compare-xsdata

# Fast test (PolyXML native engine only, skipping ~70-90s pure-Python parsers)
python3 run_benchmark.py \
    --xml NeTEx_ARR_NL_20260909_20260909_1407.xml \
    --skip-standard
```
