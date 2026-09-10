#!/usr/bin/env bash
set -euo pipefail

# Download and extract the 304MB NDOV Loket NeTEx timetable dump

DATA_URL="https://data.ndovloket.nl/netex/arr/NeTEx_ARR_NL_20260909_20260909_1407.xml.gz"
GZ_FILE="NeTEx_ARR_NL_20260909_20260909_1407.xml.gz"
XML_FILE="NeTEx_ARR_NL_20260909_20260909_1407.xml"

if [ -f "${XML_FILE}" ]; then
    echo "==> XML dataset already exists: ${XML_FILE} ($(du -h "${XML_FILE}" | cut -f1))"
    exit 0
fi

if [ ! -f "${GZ_FILE}" ]; then
    echo "==> Downloading NeTEx dataset from NDOV Loket (~12.8 MB compressed)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fSL -o "${GZ_FILE}" "${DATA_URL}"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "${GZ_FILE}" "${DATA_URL}"
    else
        echo "Error: neither curl nor wget found."
        exit 1
    fi
fi

echo "==> Decompressing ${GZ_FILE} into ${XML_FILE} (~304 MB uncompressed)..."
gunzip -k -f "${GZ_FILE}"

echo "==> Dataset successfully extracted: ${XML_FILE} ($(du -h "${XML_FILE}" | cut -f1))"
