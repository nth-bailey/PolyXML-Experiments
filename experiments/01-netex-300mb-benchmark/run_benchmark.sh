#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# End-to-end Reproduction & Benchmark Runner
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "======================================================================"
echo "⚡ Step 1: Download & Extract Live NeTEx 304MB Dataset"
echo "======================================================================"
./download_data.sh

echo ""
echo "======================================================================"
echo "⚡ Step 2: Ensure NeTEx Python Dataclass Schema is Generated"
echo "======================================================================"
if [ ! -f "netex_generated.py" ]; then
    ./generate_schema.sh pyxsdata
else
    echo "==> netex_generated.py already exists. Skipping schema generation."
fi

echo ""
echo "======================================================================"
echo "⚡ Step 3: Run 3-Way Comparative Benchmark"
echo "======================================================================"
python3 run_benchmark.py \
    --xml NeTEx_ARR_NL_20260909_20260909_1407.xml \
    --schema-file netex_generated.py \
    --compare-xsdata "$@"
