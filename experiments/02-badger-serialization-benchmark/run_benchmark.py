from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil
import multiprocessing as mp
from typing import Any, Dict, List

from mdbx import Env

# Add local experiment path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import generate_sample_stops, ScheduledStopPoint
from serializers import (
    CloudPickleSerializer,
    Pickle5Serializer,
    MsgspecSerializer,
    PolyXMLBinarySerializer,
    PipelineSerializer,
    Lz4Codec,
    ObjectSerializer,
)
from lazy_loader import benchmark_class_loading


def benchmark_pure_serialization(stops: List[ScheduledStopPoint]) -> List[Dict[str, Any]]:
    """Benchmark serialization and deserialization throughput in memory."""
    count = len(stops)
    print(f"\n--- Phase 2: In-Memory Serialization & Deserialization ({count:,} NeTEx entities) ---")

    pipelines: List[tuple[str, ObjectSerializer]] = [
        ("CloudPickle (Badger baseline)", CloudPickleSerializer()),
        ("CloudPickle + LZ4 (Badger production)", PipelineSerializer(CloudPickleSerializer(), [Lz4Codec()])),
        ("Pickle 5 + LZ4", PipelineSerializer(Pickle5Serializer(), [Lz4Codec()])),
        ("Msgspec (Tagged) + LZ4", PipelineSerializer(MsgspecSerializer(), [Lz4Codec()])),
        ("Msgspec (Typed Direct) + LZ4", PipelineSerializer(MsgspecSerializer(target_type=ScheduledStopPoint), [Lz4Codec()])),
        ("Msgspec (Typed Raw, No LZ4)", MsgspecSerializer(target_type=ScheduledStopPoint)),
        ("PolyXML Binary (Typed Direct) + LZ4", PipelineSerializer(PolyXMLBinarySerializer(target_type=ScheduledStopPoint), [Lz4Codec()])),
    ]


    results = []

    for name, serializer in pipelines:
        # Measure Dumps
        t0 = time.perf_counter()
        encoded_payloads = [serializer.dumps(s) for s in stops]
        dumps_time = time.perf_counter() - t0

        total_bytes = sum(len(b) for b in encoded_payloads)
        avg_payload_size = total_bytes / count
        dumps_ops_sec = count / dumps_time
        dumps_mb_sec = (total_bytes / (1024 * 1024)) / dumps_time

        # Measure Loads
        t0 = time.perf_counter()
        decoded_objs = [serializer.loads(b) for b in encoded_payloads]
        loads_time = time.perf_counter() - t0

        loads_ops_sec = count / loads_time
        loads_mb_sec = (total_bytes / (1024 * 1024)) / loads_time

        # Verify correctness
        assert decoded_objs[0] == stops[0], f"Integrity check failed for {name}"

        res = {
            "name": name,
            "dumps_time_s": dumps_time,
            "dumps_ops_sec": dumps_ops_sec,
            "dumps_mb_sec": dumps_mb_sec,
            "loads_time_s": loads_time,
            "loads_ops_sec": loads_ops_sec,
            "loads_mb_sec": loads_mb_sec,
            "avg_payload_size_bytes": avg_payload_size,
            "total_bytes": total_bytes,
        }
        results.append(res)

        print(f"  {name:38s} | Dumps: {dumps_ops_sec:8,.0f} ops/s ({dumps_mb_sec:5.1f} MB/s) | Loads: {loads_ops_sec:8,.0f} ops/s ({loads_mb_sec:5.1f} MB/s) | Size: {avg_payload_size:4.0f} B")

    return results


def benchmark_mdbx_storage(stops: List[ScheduledStopPoint]) -> List[Dict[str, Any]]:
    """Benchmark actual MDBX key-value database operations using different serializers."""
    count = len(stops)
    print(f"\n--- Phase 3: MDBX Key-Value Database Pipeline ({count:,} entities) ---")

    pipelines: List[tuple[str, ObjectSerializer]] = [
        ("CloudPickle + LZ4 (Badger production)", PipelineSerializer(CloudPickleSerializer(), [Lz4Codec()])),
        ("Msgspec (Tagged) + LZ4", PipelineSerializer(MsgspecSerializer(), [Lz4Codec()])),
        ("Msgspec (Typed) + LZ4", PipelineSerializer(MsgspecSerializer(target_type=ScheduledStopPoint), [Lz4Codec()])),
        ("PolyXML Binary (Typed) + LZ4", PipelineSerializer(PolyXMLBinarySerializer(target_type=ScheduledStopPoint), [Lz4Codec()])),
    ]


    results = []

    for name, serializer in pipelines:
        temp_dir = tempfile.mkdtemp(prefix="badger_mdbx_bench_")
        db_path = os.path.join(temp_dir, "benchmark.mdbx")

        try:
            env = Env(db_path, maxdbs=16)

            # Insert Phase
            t0 = time.perf_counter()
            with env.rw_transaction() as txn:
                with txn.create_map(b"scheduled_stops") as db:
                    for s in stops:
                        key = s.id.encode("utf-8")
                        val = serializer.dumps(s)
                        db.put(txn, key, val)
                txn.commit()
            insert_time = time.perf_counter() - t0
            insert_ops_sec = count / insert_time

            # Read / Scan Phase
            t0 = time.perf_counter()
            retrieved = 0
            with env.ro_transaction() as txn:
                with txn.open_map(b"scheduled_stops") as db:
                    with txn.cursor(db) as cur:
                        for key, val in cur.iter():
                            obj = serializer.loads(val)
                            retrieved += 1
            read_time = time.perf_counter() - t0
            read_ops_sec = count / read_time

            env.close()

            # Check DB file size
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)

            res = {
                "name": name,
                "insert_time_s": insert_time,
                "insert_ops_sec": insert_ops_sec,
                "read_time_s": read_time,
                "read_ops_sec": read_ops_sec,
                "db_size_mb": db_size_mb,
            }
            results.append(res)

            print(f"  {name:38s} | MDBX Write: {insert_ops_sec:7,.0f} ops/s ({insert_time*1000:6.1f} ms) | MDBX Read: {read_ops_sec:7,.0f} ops/s ({read_time*1000:6.1f} ms) | DB Size: {db_size_mb:.2f} MB")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results


def _worker_deserialize_task(serializer_type: str, chunks: List[bytes]) -> int:
    """Worker task deserializing a chunk of byte buffers."""
    if serializer_type == "cloudpickle":
        serializer = PipelineSerializer(CloudPickleSerializer(), [Lz4Codec()])
    else:
        serializer = PipelineSerializer(MsgspecSerializer(), [Lz4Codec()])

    count = 0
    for b in chunks:
        obj = serializer.loads(b)
        count += 1
    return count


def benchmark_multiprocessing(stops: List[ScheduledStopPoint], worker_counts: List[int] = [1, 2, 4]) -> Dict[str, Any]:
    """Benchmark deserialization scaling across multiprocessing workers."""
    count = len(stops)
    print(f"\n--- Phase 4: Multiprocessing Worker Scaling ({count:,} entities) ---")

    # Pre-serialize payloads
    cp_ser = PipelineSerializer(CloudPickleSerializer(), [Lz4Codec()])
    ms_ser = PipelineSerializer(MsgspecSerializer(), [Lz4Codec()])

    cp_payloads = [cp_ser.dumps(s) for s in stops]
    ms_payloads = [ms_ser.dumps(s) for s in stops]

    results = {}

    for workers in worker_counts:
        # CloudPickle in multiprocessing
        chunk_size = count // workers
        cp_chunks = [cp_payloads[i * chunk_size : (i + 1) * chunk_size] for i in range(workers)]
        ms_chunks = [ms_payloads[i * chunk_size : (i + 1) * chunk_size] for i in range(workers)]

        ctx = mp.get_context("fork")

        # Test CloudPickle
        t0 = time.perf_counter()
        with ctx.Pool(workers) as pool:
            tasks = [pool.apply_async(_worker_deserialize_task, ("cloudpickle", chunk)) for chunk in cp_chunks]
            _ = [t.get() for t in tasks]
        cp_time = time.perf_counter() - t0
        cp_ops = count / cp_time

        # Test Msgspec
        t0 = time.perf_counter()
        with ctx.Pool(workers) as pool:
            tasks = [pool.apply_async(_worker_deserialize_task, ("msgspec", chunk)) for chunk in ms_chunks]
            _ = [t.get() for t in tasks]
        ms_time = time.perf_counter() - t0
        ms_ops = count / ms_time

        speedup = ms_ops / cp_ops
        results[workers] = {
            "cp_ops": cp_ops,
            "cp_time_s": cp_time,
            "ms_ops": ms_ops,
            "ms_time_s": ms_time,
            "speedup": speedup,
        }

        print(f"  Workers: {workers} | CloudPickle: {cp_ops:8,.0f} ops/s ({cp_time*1000:6.1f} ms) | Msgspec: {ms_ops:8,.0f} ops/s ({ms_time*1000:6.1f} ms) | ⚡ Speedup: {speedup:4.1f}x")

    return results


def main():
    print("================================================================================")
    print("🚀 Badger NeTEx Optimization Benchmark: Class Loading & MDBX Serialization")
    print("   Evaluating CloudPickle baseline vs. Msgspec in C & Lazy Class Dispatcher")
    print("================================================================================")

    # Phase 1: Class Loading
    print("\n--- Phase 1: Class Startup & Loading (2,000 NeTEx Dataclasses) ---")
    loading_res = benchmark_class_loading(class_count=2000)
    print(f"  Eager Import (Badger current):  {loading_res['eager_import_ms']:8.2f} ms")
    print(f"  Lazy Import (PEP 562 proposed): {loading_res['lazy_import_ms']:8.2f} ms")
    print(f"  ⚡ Cold Start Speedup:         {loading_res['speedup_factor']:8.1f}x faster")
    print(f"  First Entity Access:            {loading_res['lazy_first_access_ms']:8.2f} ms")
    print(f"  Cached Entity Access:           {loading_res['lazy_cached_access_ms']:8.4f} ms")

    # Generate test dataset
    stops = generate_sample_stops(count=10_000)

    # Phase 2: Serialization
    pure_res = benchmark_pure_serialization(stops)

    # Phase 3: MDBX
    mdbx_res = benchmark_mdbx_storage(stops)

    # Phase 4: Multiprocessing
    mp_res = benchmark_multiprocessing(stops, worker_counts=[1, 2, 4])

    # Summary calculations
    baseline_pure = pure_res[1]   # CloudPickle + LZ4
    msgspec_tagged = pure_res[3]  # Msgspec (Tagged) + LZ4
    msgspec_typed = pure_res[4]   # Msgspec (Typed) + LZ4
    msgspec_raw = pure_res[5]     # Msgspec (Raw)

    dumps_speedup_tagged = msgspec_tagged['dumps_ops_sec'] / baseline_pure['dumps_ops_sec']
    loads_speedup_tagged = msgspec_tagged['loads_ops_sec'] / baseline_pure['loads_ops_sec']
    dumps_speedup_typed = msgspec_typed['dumps_ops_sec'] / baseline_pure['dumps_ops_sec']
    loads_speedup_typed = msgspec_typed['loads_ops_sec'] / baseline_pure['loads_ops_sec']
    dumps_speedup_raw = msgspec_raw['dumps_ops_sec'] / baseline_pure['dumps_ops_sec']
    loads_speedup_raw = msgspec_raw['loads_ops_sec'] / baseline_pure['loads_ops_sec']

    baseline_mdbx = mdbx_res[0]
    fast_mdbx = mdbx_res[1]
    mdbx_write_speedup = fast_mdbx['insert_ops_sec'] / baseline_mdbx['insert_ops_sec']
    mdbx_read_speedup = fast_mdbx['read_ops_sec'] / baseline_mdbx['read_ops_sec']

    print("\n================================================================================")
    print("📊 EXECUTIVE BENCHMARK SUMMARY (BEFORE VS. AFTER)")
    print("================================================================================")
    print(f"1. Class Startup Time:       {loading_res['eager_import_ms']:7.1f} ms  -->  {loading_res['lazy_import_ms']:5.1f} ms ({loading_res['speedup_factor']:.1f}x faster)")
    print(f"2. Pure Serialization (Dumps):")
    print(f"   - Tagged (Drop-in):       {baseline_pure['dumps_ops_sec']:7,.0f} ops/s --> {msgspec_tagged['dumps_ops_sec']:7,.0f} ops/s ({dumps_speedup_tagged:4.1f}x faster)")
    print(f"   - Typed Direct:           {baseline_pure['dumps_ops_sec']:7,.0f} ops/s --> {msgspec_typed['dumps_ops_sec']:7,.0f} ops/s ({dumps_speedup_typed:4.1f}x faster)")
    print(f"   - Raw MessagePack (No LZ4):{baseline_pure['dumps_ops_sec']:6,.0f} ops/s --> {msgspec_raw['dumps_ops_sec']:7,.0f} ops/s ({dumps_speedup_raw:4.1f}x faster)")
    print(f"3. Pure Deserialization (Loads):")
    print(f"   - Tagged (Drop-in):       {baseline_pure['loads_ops_sec']:7,.0f} ops/s --> {msgspec_tagged['loads_ops_sec']:7,.0f} ops/s ({loads_speedup_tagged:4.1f}x faster)")
    print(f"   - Typed Direct:           {baseline_pure['loads_ops_sec']:7,.0f} ops/s --> {msgspec_typed['loads_ops_sec']:7,.0f} ops/s ({loads_speedup_typed:4.1f}x faster)")
    print(f"   - Raw MessagePack (No LZ4):{baseline_pure['loads_ops_sec']:6,.0f} ops/s --> {msgspec_raw['loads_ops_sec']:7,.0f} ops/s ({loads_speedup_raw:4.1f}x faster)")
    print(f"4. Real MDBX Database:")
    print(f"   - Write Throughput:       {baseline_mdbx['insert_ops_sec']:7,.0f} ops/s --> {fast_mdbx['insert_ops_sec']:7,.0f} ops/s ({mdbx_write_speedup:4.1f}x faster)")
    print(f"   - Read / Scan Throughput: {baseline_mdbx['read_ops_sec']:7,.0f} ops/s --> {fast_mdbx['read_ops_sec']:7,.0f} ops/s ({mdbx_read_speedup:4.1f}x faster)")
    print(f"5. Storage Footprint per Stop: {baseline_pure['avg_payload_size_bytes']:4.0f} B  -->  {msgspec_tagged['avg_payload_size_bytes']:4.0f} B ({(1.0 - msgspec_tagged['avg_payload_size_bytes']/baseline_pure['avg_payload_size_bytes'])*100:.1f}% space savings)")
    print(f"6. Multiprocessing (4 cores): {mp_res[4]['cp_ops']:7,.0f} ops/s --> {mp_res[4]['ms_ops']:7,.0f} ops/s ({mp_res[4]['speedup']:4.1f}x faster)")
    print("================================================================================")


if __name__ == "__main__":
    main()
