#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Generate Python dataclass bindings from NeTEx v2.0 Technical Standard
# Supports code generation via either:
#   1. pyxsdata (default, recommended): Native modern bindings generator
#   2. xsdata: Predecessor generator (requires post-processing patch for metadata defaults)
# ==============================================================================

TOOL="${1:-pyxsdata}" # default to pyxsdata, or pass "xsdata"

echo "======================================================================"
echo "⚡ NeTEx Schema Code Generation"
echo "   Generator Engine: ${TOOL}"
echo "======================================================================"

# 1. Clone NeTEx v2.0 schema repository if missing
if [ ! -d "NeTEx" ]; then
    echo "==> [1/3] Cloning NeTEx v2.0 schema repository from GitHub..."
    git clone --depth 1 --branch v2.0 https://github.com/TransmodelEcosystem/NeTEx.git NeTEx
else
    echo "==> [1/3] NeTEx schema repository already present."
fi

# 2. Compile schema using the selected generator
SCHEMA_ENTRY="NeTEx/xsd/NeTEx_publication.xsd"
OUTPUT_FILE="netex_generated.py"

if [ "${TOOL}" = "pyxsdata" ]; then
    echo "==> [2/3] Compiling ${SCHEMA_ENTRY} with pyxsdata..."
    pyxsdata generate "${SCHEMA_ENTRY}" \
        -p netex_generated \
        --structure-style single-package

elif [ "${TOOL}" = "xsdata" ]; then
    echo "==> [2/3] Compiling ${SCHEMA_ENTRY} with predecessor xsdata..."
    xsdata generate "${SCHEMA_ENTRY}" \
        -p netex_generated \
        --structure-style single-package

    echo "==> [2.5/3] Applying patch for xsdata unquoted metadata default bug..."
    # Upstream xsdata <= 26.2 emits unquoted tokens for metadata string defaults
    # (e.g. "default": optional instead of "default": "optional"), causing NameError on import.
    sed -i 's/"default": optional/"default": "optional"/g' "${OUTPUT_FILE}"
else
    echo "Error: Unknown generator tool '${TOOL}'. Use 'pyxsdata' or 'xsdata'."
    exit 1
fi

# 3. Verify that the generated module imports cleanly into Python
echo "==> [3/3] Validating Python import of ${OUTPUT_FILE}..."
python3 -c "import ${OUTPUT_FILE%.py}; print(f'✓ Successfully loaded {len(dir(netex_generated))} symbols from {OUTPUT_FILE%.py}')"

echo "======================================================================"
echo "✅ Schema successfully generated and validated: ${OUTPUT_FILE}"
echo "======================================================================"
