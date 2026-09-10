# PolyXML Experiments & Real-World Benchmarks

This repository contains independent stress tests, scalability benchmarks, and real-world schema evaluations for [PolyXML](https://github.com/nth-bailey/PolyXML)—the high-performance, polyglot native XML data-binding engine.

---

## Experiments Index

| # | Experiment Name | Focus Area | Key Finding |
|---|---|---|---|
| **01** | [NeTEx 304MB European Transit Benchmark](experiments/01-netex-300mb-benchmark/) | High-throughput streaming, large real-world CEN transit models, memory consumption | **244.7x faster** than predecessor `xsdata` (845 MB/s vs 3.45 MB/s) & **~75% less RAM** (~1.27 GB saved). |

---

## About PolyXML
PolyXML provides zero-copy, high-throughput bidirectional XML serialization and deserialization across programming languages (Rust, Python, Node.js, Java, C++, and Go). In the Python ecosystem, it serves as the drop-in native backend for [pyxsdata](https://github.com/nth-bailey/pyxsdata) dataclasses and Pydantic models via `CoreXmlParser` and `CoreXmlSerializer`.
