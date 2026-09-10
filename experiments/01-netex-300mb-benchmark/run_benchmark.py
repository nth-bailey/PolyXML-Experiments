"""Comparative benchmark: PolyXML native engine vs pyxsdata vs predecessor xsdata on NeTEx datasets."""

import argparse
import gc
import os
import resource
import sys
import time
from pathlib import Path


def get_peak_rss_mb() -> float:
    """Return peak resident set size in megabytes."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def parse_args():
    parser = argparse.ArgumentParser(description="NeTEx 300MB Benchmark Runner")
    parser.add_argument(
        "--xml",
        type=Path,
        default=Path("NeTEx_ARR_NL_20260909_20260909_1407.xml"),
        help="Path to NeTEx XML file",
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path("netex_generated.py"),
        help="Path to generated Python dataclass file",
    )
    parser.add_argument(
        "--skip-standard",
        action="store_true",
        help="Skip the standard pure-Python parser benchmarks (which take >70-90s each)",
    )
    parser.add_argument(
        "--compare-xsdata",
        action="store_true",
        help="Include benchmark against predecessor xsdata library",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.xml.exists():
        print(f"Error: XML file not found at {args.xml}")
        print("Download it with:")
        print("  wget https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz")
        print("  gunzip NeTEx_ARR_NL_20260909_20260909_1407.xml.gz")
        sys.exit(1)

    # Add schema location to sys.path
    schema_dir = args.schema_file.resolve().parent
    sys.path.insert(0, str(schema_dir))

    print(f"Loading schema from {args.schema_file.name}...")
    t0 = time.perf_counter()
    try:
        from netex_generated import PublicationDelivery
    except ImportError as e:
        print(f"Failed to import PublicationDelivery: {e}")
        print("Ensure you generated the schema via ./generate_schema.sh")
        sys.exit(1)
    print(f"Schema imported in {time.perf_counter() - t0:.2f}s\n")

    from pyxsdata.formats.dataclass.parsers import CoreXmlParser, XmlParser as PyxsdataXmlParser

    file_size_mb = args.xml.stat().st_size / (1024 * 1024)

    # 1. Benchmark PolyXML Native Engine
    print("==================================================")
    print("  1. PolyXML Native Engine (CoreXmlParser)")
    print(f"  Target File: {args.xml.name} ({file_size_mb:.2f} MB)")
    print("==================================================")
    gc.collect()
    rss_before_poly = get_peak_rss_mb()
    t_start = time.perf_counter()

    poly_parser = CoreXmlParser()
    poly_result = poly_parser.from_path(args.xml, PublicationDelivery)

    t_poly = time.perf_counter() - t_start
    rss_after_poly = get_peak_rss_mb()
    poly_throughput = file_size_mb / t_poly

    print(f"⚡ Time Elapsed:     {t_poly:.3f} seconds")
    print(f"⚡ Throughput:       {poly_throughput:.2f} MB/s")
    print(f"⚡ Peak RSS Memory:  {rss_after_poly:.2f} MB (delta: +{rss_after_poly - rss_before_poly:.2f} MB)")
    print(f"✓ Root Type:        {type(poly_result).__name__}")
    print(f"✓ Description:      {getattr(poly_result, 'description', None)}")
    print(f"✓ Timestamp:        {getattr(poly_result, 'publication_timestamp', None)}")
    print(f"✓ Participant:      {getattr(poly_result, 'participant_ref', None)}")
    print(f"✓ Has DataObjects:  {hasattr(poly_result, 'data_objects') and poly_result.data_objects is not None}")

    if args.skip_standard:
        print("\nSkipping standard pure-Python parser benchmark (--skip-standard passed).")
        return

    # 2. Benchmark Default pyxsdata pure-Python parser
    print("\n==================================================")
    print("  2. Default pyxsdata XmlParser (Pure Python)")
    print(f"  Target File: {args.xml.name}")
    print("==================================================")
    gc.collect()
    rss_before_std = get_peak_rss_mb()
    t_start = time.perf_counter()

    std_parser = PyxsdataXmlParser()
    print("Executing pyxsdata parser (takes ~70s)...")
    std_result = std_parser.from_path(args.xml, PublicationDelivery)

    t_std = time.perf_counter() - t_start
    rss_after_std = get_peak_rss_mb()
    std_throughput = file_size_mb / t_std

    print(f"Standard Time:       {t_std:.3f} seconds")
    print(f"Standard Throughput: {std_throughput:.2f} MB/s")
    print(f"Standard Peak RSS:   {rss_after_std:.2f} MB")

    # 3. Benchmark Predecessor xsdata (if requested)
    t_xsd, std_xsd_speed, rss_xsd = None, None, None
    if args.compare_xsdata:
        print("\n==================================================")
        print("  3. Predecessor xsdata XmlParser (Pure Python)")
        print(f"  Target File: {args.xml.name}")
        print("==================================================")
        try:
            import pyxsdata.models.datatype
            sys.modules["xsdata.models.datatype"] = pyxsdata.models.datatype
            from xsdata.formats.converter import converter

            for attr in ["XmlDate", "XmlDateTime", "XmlTime", "XmlDuration", "XmlPeriod"]:
                cls = getattr(pyxsdata.models.datatype, attr)
                converter.register_converter(cls, converter.type_converter(cls))

            from xsdata.formats.dataclass.parsers import XmlParser as XsdataXmlParser

            gc.collect()
            t_start = time.perf_counter()
            xsd_parser = XsdataXmlParser()
            print("Executing predecessor xsdata parser (takes ~88s)...")
            xsd_parser.from_path(args.xml, PublicationDelivery)
            t_xsd = time.perf_counter() - t_start
            rss_xsd = get_peak_rss_mb()
            std_xsd_speed = file_size_mb / t_xsd
            print(f"xsdata Time:         {t_xsd:.3f} seconds")
            print(f"xsdata Throughput:   {std_xsd_speed:.2f} MB/s")
            print(f"xsdata Peak RSS:     {rss_xsd:.2f} MB")
        except ImportError:
            print("xsdata is not installed. Install via `pip install xsdata` to include it.")

    # Summary
    print("\n==================================================")
    print("  SUMMARY & SPEEDUP COMPARISON")
    print("==================================================")
    print(f"🚀 PolyXML vs pyxsdata: {t_std / t_poly:.1f}x FASTER")
    if t_xsd:
        print(f"🚀 PolyXML vs xsdata:   {t_xsd / t_poly:.1f}x FASTER")
    ram_reduction = (1.0 - (rss_after_poly / rss_after_std)) * 100
    print(f"🚀 Peak RAM Reduction:  {ram_reduction:.1f}% LESS memory used by PolyXML")
    print("==================================================")


if __name__ == "__main__":
    main()
