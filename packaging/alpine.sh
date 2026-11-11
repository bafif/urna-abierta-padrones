#!/bin/sh
# Prepares, inside an Alpine 3.24 container, the Python that builds the reader for Alpine and the other Linux with
# musl (urna-abierta-lector-linux-x64-musl). Then packaging/build.py builds it as on any other system:
#   podman run --rm -v "$PWD":/src -w /src docker.io/library/alpine:3.24 \
#     sh -c 'sh packaging/alpine.sh && /opt/lector/bin/python packaging/build.py --self-test --archive'
# PyPI publishes no onnxruntime and no OpenCV for musl, nor pyclipper for Alpine's Python: those three and numpy (which
# they are built against) come from Alpine's packages. Everything else, PyInstaller included, at the versions in
# uv.lock, from their musl wheels.
set -eu
apk add --no-cache python3 py3-onnxruntime py3-opencv py3-numpy py3-pyclipper uv binutils git
python3 -m venv --system-site-packages /opt/lector
uv export --frozen --no-dev --group build --no-emit-project --no-hashes --format requirements.txt \
  | grep -Ev '^(#|numpy|onnxruntime|opencv-python-headless|flatbuffers|protobuf|pyclipper)' > /tmp/lector-requisitos.txt
uv pip install --python /opt/lector/bin/python --no-deps -r /tmp/lector-requisitos.txt
uv pip install --python /opt/lector/bin/python --no-deps .
