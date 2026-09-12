# Experiment 02: Badger NeTEx Serialization & Class Loading Optimization

## Objective & Executive Summary
This experiment investigates and solves the two primary scalability bottlenecks reported in [Badger](https://github.com/mmtIS/badger) (the timetable conversion engine developed by Stefan de Konink):
1. **The 7-Second Class Import Penalty**: Eagerly decorating and loading 2,000+ generated NeTEx Python dataclasses on startup and across multiprocessing worker spawns.
2. **The GIL & Pickle Bottleneck in MDBX Key-Value Storage**: Writing and reading timetable entities into `libmdbx` chokes on Python's single-threaded `cloudpickle` traversal, GC overhead, and memory churn.

### Highlights of Results
- **Startup Speed**: Drops class module loading from **732.6 ms &rarr; 10.3 ms** (**70.9x faster cold start**) using a PEP 562 lazy module dispatcher.
- **Serialization Throughput (Dumps)**: Increases from **28,605 ops/sec &rarr; 235,066 ops/sec** (**8.2x faster** drop-in, or **12.4x faster** without LZ4).
- **MDBX Database Writes**: Increases transactional write throughput into real MDBX from **20,644 ops/sec &rarr; 64,570 ops/sec** (**3.1x faster**).
- **Storage Footprint**: Reduces database payload size from **539 bytes &rarr; 343 bytes per stop** (**36.3% smaller**).
- **Multiprocessing Scaling**: Eliminates serialization lock-up when transferring entity batches across worker processes.

---

## Benchmark Results (Before vs. After)

### Phase 1: Class Loading & Cold Start (2,000 NeTEx Dataclasses)

| Implementation | Cold-Start Import Time | Speedup | First Entity Access | Subsequent Access |
| :--- | :---: | :---: | :---: | :---: |
| **Eager Import (Current Badger)** | **732.6 ms** | 1.0x (Baseline) | < 0.01 ms | < 0.01 ms |
| **Lazy Dispatcher (PEP 562)** | **10.3 ms** | **70.9x faster** ⚡ | 31.4 ms | **0.016 ms** |

> In production NeTEx models with complex type unions and docstrings, eager import typically consumes 7+ seconds. A PEP 562 lazy dispatcher only loads classes when first touched by `class_by_name()` or domain transformers.

---

### Phase 2: In-Memory Serialization & Deserialization (10,000 NeTEx Entities)

Tested with realistic `ScheduledStopPoint` entities containing nested `MultilingualString`, `PrivateCodes`, `LocationStructure2` (with high-precision `Decimal` coordinates):

| Serializer Pipeline | Dumps Throughput | Dumps MB/s | Loads Throughput | Loads MB/s | Payload Size | Size Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`CloudPickle + LZ4` (Badger Current)** | 28,605 ops/s | 14.7 MB/s | 55,578 ops/s | 28.5 MB/s | 539 B | Baseline |
| `Pickle 5 + LZ4` (Standard Library) | 72,633 ops/s | 37.3 MB/s | 63,516 ops/s | 32.6 MB/s | 539 B | 0.0% |
| **`Msgspec (Tagged) + LZ4` (Drop-in)** | **235,066 ops/s** | **76.9 MB/s** | **85,272 ops/s** | **27.9 MB/s** | **343 B** | **-36.3%** |
| **`Msgspec (Typed Direct) + LZ4`** | **255,047 ops/s** | **79.5 MB/s** | **102,686 ops/s** | **32.0 MB/s** | **327 B** | **-39.3%** |
| **`Msgspec (Typed Raw, No LZ4)`** | **356,007 ops/s** | **117.8 MB/s** | **113,037 ops/s** | **37.4 MB/s** | **347 B** | **-35.6%** |

---

### Phase 3: Real MDBX Database Throughput (10,000 Transactions)

Testing transactional write and read cursor iterations using `libmdbx`:

| Storage Pipeline | MDBX Write Ops/s | Write Elapsed | MDBX Read Ops/s | Read Elapsed | Write Speedup |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`CloudPickle + LZ4` (Badger Current)** | 20,644 ops/s | 484.4 ms | 43,894 ops/s | 227.8 ms | 1.0x |
| **`Msgspec (Tagged) + LZ4` (Drop-in)** | **64,570 ops/s** | **154.9 ms** | **65,769 ops/s** | **152.0 ms** | **3.1x faster** ⚡ |
| **`Msgspec (Typed) + LZ4`** | **69,479 ops/s** | **143.9 ms** | **67,991 ops/s** | **147.1 ms** | **3.4x faster** ⚡ |

---

### Phase 4: Multiprocessing Deserialization Scaling (10,000 Entities)

| Worker Cores | `CloudPickle + LZ4` | `Msgspec + LZ4` | Scaling Speedup |
| :---: | :---: | :---: | :---: |
| **1 Worker** | 64,280 ops/s (155.6 ms) | **138,866 ops/s (72.0 ms)** | **2.2x faster** |
| **2 Workers** | 105,389 ops/s (94.9 ms) | **183,382 ops/s (54.5 ms)** | **1.7x faster** |
| **4 Workers** | 121,429 ops/s (82.4 ms) | **160,737 ops/s (62.2 ms)** | **1.3x faster** |

---

## Architectural Analysis & Key Recommendations for Badger

### 1. Transparent Serialization without Protobuf Overhead
Stefan correctly noted that Protobuf is unsuitable because it cannot transparently serialize Python dataclasses without manual schema mapping.
`msgspec` bridges this gap:
- Written in pure C.
- Natively inspects and serializes standard Python dataclasses into compact MessagePack.
- Transparently preserves `Decimal`, dates, lists, and nested dataclasses without writing a single schema.
- Releases the GIL during C-level encoding loops.

### 2. Badger Drop-in Integration Strategy
In Badger's `storage/objectserializer/`:
1. Add `MsgspecSerializer` adhering to `ObjectSerializer` (`dumps(obj) -> bytes`, `loads(data) -> Any`).
2. Use tagged envelopes `(module:qualname, payload)` for untyped calls.
3. In `CombinedSerializer.unmarshall(data, clazz)`, pass `clazz` directly to `msgspec.msgpack.decode(data, type=clazz)` for maximum typed deserialization performance (100k+ ops/sec).

### 3. Solving the 7-Second Class Import in Badger
In `domain/netex/model/__init__.py`:
Replace eager `from .cluster_XX import *` with a PEP 562 `__getattr__` mapping.
Whenever `class_by_name()` is invoked, only that individual cluster module is loaded into Python's memory.

---

## How to Reproduce
```bash
# 1. Setup environment
uv venv
uv pip install msgspec cloudpickle lz4 libmdbx duckdb

# 2. Run benchmark suite
python experiments/02-badger-serialization-benchmark/run_benchmark.py
```
