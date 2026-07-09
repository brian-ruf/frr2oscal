#!/usr/bin/env bash
# ============================================================
#  frr2oscal – Linux/Ubuntu Run Script
#  Reads the FedRAMP Rules JSON file from the official repo
#  Produces: an OSCAL catalog and profiles
#
#  Usage:
#    ./run.sh           - quick run (builds if needed)
#    ./run.sh --clean   - wipe pycache first
# ============================================================

set -euo pipefail

# ── Activate the Ubuntu venv ─────────────────────────────────
if [[ -f ".venv/bin/activate" ]]; then
    echo "Using existing virtual environment..."
    source .venv/bin/activate
else
    echo "[ERROR] No venv found. Creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
    ./venv_setup.sh
fi

cd src

# ── Optional clean ───────────────────────────────────────────
if [[ "${1:-}" == "--clean" ]]; then
    echo "[RUN] Cleaning pycache..."
    rm -rf build dist __pycache__
fi


# ── Build ────────────────────────────────────────────────────
echo "[RUN] Running Converter ..."
python -m frr2oscal


echo ""
