# !/bin/bash

set -euo pipefail

rm -rf ${DISTRIBUTION_DIR} build *.egg-info **/__pycache__
mkdir -p ${DISTRIBUTION_DIR}
echo "${VERSION}" > "${DISTRIBUTION_DIR}/VERSION.txt"
pip wheel build --no-deps --no-input --no-binary :all: --wheel-dir ${DISTRIBUTION_DIR} .
