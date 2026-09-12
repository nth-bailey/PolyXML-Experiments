# PolyXML Experiments & Real-World Benchmarks

This repository contains independent stress tests, scalability benchmarks, and real-world schema evaluations for [PolyXML](https://github.com/nth-bailey/PolyXML)—the high-performance, polyglot native XML data-binding engine.

---

## Experiments Index

| # | Experiment Name | Focus Area | Key Finding |
|---|---|---|---|
| **01** | [NeTEx 304MB European Transit Benchmark](experiments/01-netex-300mb-benchmark/) | High-throughput streaming, large real-world CEN transit models, memory consumption | **845 MB/s streaming throughput** (0.360s vs 88.0s predecessor `xsdata`) & **~75% less RAM** (~1.27 GB saved). |
| **02** | [Badger NeTEx Serialization & Class Loading Optimization](experiments/02-badger-serialization-benchmark/) | MDBX storage serialization (`msgspec` vs `cloudpickle`), PEP 562 lazy class loading | **8.2x faster serialization** (235k ops/s vs 28k ops/s), **3.1x faster MDBX writes**, **36% smaller storage**, and **70.9x faster cold start** (10ms vs 732ms). |

---

## About PolyXML
PolyXML provides zero-copy, high-throughput bidirectional XML serialization and deserialization across programming languages (Rust, Python, Node.js, Java, C++, and Go). In the Python ecosystem, it serves as the drop-in native backend for [pyxsdata](https://github.com/nth-bailey/pyxsdata) dataclasses and Pydantic models via `CoreXmlParser` and `CoreXmlSerializer`.
