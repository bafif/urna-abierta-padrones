import os

# The tests import the reading engine in any order; onnxruntime's telemetry stays off anyway.
# test_ocr.py checks that the package turns it off by itself.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
