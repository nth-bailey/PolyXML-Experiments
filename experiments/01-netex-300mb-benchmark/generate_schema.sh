#!/usr/bin/env bash
set -euo pipefail

# This script clones the official NeTEx v2.0 repository and generates
# the Python dataclass bindings using pyxsdata.

echo "==> Cloning NeTEx v2.0 schema repository..."
if [ ! -d "NeTEx" ]; then
    git clone --depth 1 --branch v2.0 https://github.com/TransmodelEcosystem/NeTEx.git NeTEx
fi

echo "==> Compiling NeTEx_publication.xsd into Python dataclasses via pyxsdata..."
pyxsdata generate NeTEx/xsd/NeTEx_publication.xsd --output-format dataclasses --output netex_generated.py

echo "==> Schema successfully generated: netex_generated.py"
