# Experiment 01: NeTEx 304MB European Transit Benchmark

## Objective & Background
This benchmark tests the performance, scalability, and memory consumption of the native **PolyXML** engine against standard pure-Python XML binding libraries on massive, highly complex XML data structures.

The test was conducted using:
1. **Schema**: The European Committee for Standardization (CEN) **NeTEx v2.0** Technical Standard ([CEN/TS 16614](https://netex-cen.eu/)), starting from [`NeTEx_publication.xsd`](https://github.com/TransmodelEcosystem/NeTEx/blob/v2.0/xsd/NeTEx_publication.xsd).
2. **Dataset**: A **303.92 MB** national timetable publication dump from the Dutch National Public Transport Data Portal (NDOV Loket / Arriva NL): `NeTEx_ARR_NL_20260909_20260909_1407.xml`.

---

## Benchmark Results

| Metric | PolyXML Native Engine (`CoreXmlParser`) | Standard `pyxsdata` (`XmlParser`) | Delta / Improvement |
|:---|:---:|:---:|:---:|
| **Parse Time** | **0.463 seconds** | **93.565 seconds** | **202.1x FASTER** :rocket: |
| **Throughput** | **656.53 MB/s** | **3.25 MB/s** | **~200x Higher Bandwidth** |
| **Peak RAM (RSS)** | **442.21 MB** | **1,718.59 MB** | **~74% Less Memory** |
| **Data Integrity** | :white_check_mark: Full Extraction | :white_check_mark: Full Extraction | Identical Output |

---

## Test Environment & Hardware Specifications

- **Processor (CPU)**: AMD Ryzen 5 4500 6-Core Processor (12 threads @ 3.6 GHz base)
- **RAM**: 8 GB
- **Operating System**: Linux x86_64 (Kernel 6.6.x)
- **Python Runtime**: CPython 3.12.14
- **Libraries**:
  - `polyxml` v0.3.0 (`quick-xml` 0.37.5, `pyo3` 0.23.5)
  - `pyxsdata` v1.4.0

---

## Dataset References & Reproducibility

### 1. NeTEx XML Schema Definition (XSD)
- **Upstream Repository**: [TransmodelEcosystem/NeTEx (Release v2.0)](https://github.com/TransmodelEcosystem/NeTEx/tree/v2.0)
- **Primary Schema Entrypoint**: [`xsd/NeTEx_publication.xsd`](https://github.com/TransmodelEcosystem/NeTEx/blob/v2.0/xsd/NeTEx_publication.xsd)
- **Generated Model**: Compiled with `pyxsdata` into `netex_generated.py` (>232,000 lines of standard Python dataclasses, root model `PublicationDelivery`).

### 2. Live Transit Data Source
- **Provider**: NDOV Loket (Netherlands National Public Transport Database)
- **Download URL**: [`https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz`](https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz)
- **File Size**: 12.8 MB compressed (.gz) / 303.92 MB uncompressed (.xml)

---

## Why PolyXML Achieves 200x Performance

1. **Streaming Token Extraction without DOM Allocation**:
   Standard parsers construct an intermediate DOM or Python element dictionary before instantiating target classes. PolyXML uses pure Rust streaming events (`quick-xml`) with SIMD-accelerated delimiter scanning.
2. **Zero-Allocation Byte Conversions**:
   Numerical fields (timestamps, delays, sequence indices, coordinates) are parsed directly from raw UTF-8 byte slices using `lexical-core`, bypassing Python string allocation.
3. **Direct PyO3 Constructor Invocations**:
   Target Python dataclass instances are constructed directly from Rust using PyO3 0.23 `Bound` APIs without intermediate dictionary overhead, drastically cutting garbage collection pressure and reducing peak RSS by ~1.3 GB.

---

## How to Run This Benchmark

### Prerequisites
```bash
pip install -r requirements.txt
```

### 1. Generate Schema
```bash
./generate_schema.sh
```

### 2. Download Data & Execute
```bash
wget https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz
gunzip NeTEx_ARR_NL_20260909_20260909_1407.xml.gz

python run_benchmark.py --xml NeTEx_ARR_NL_20260909_20260909_1407.xml
```
