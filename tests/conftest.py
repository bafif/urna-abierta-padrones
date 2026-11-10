import atexit
import os
import shutil
import tempfile

import pytest

# The tests import the reading engine in any order; onnxruntime's telemetry stays off anyway.
# test_ocr.py checks that the package turns it off by itself.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

# What the reader remembers goes to a folder of the tests, never to the home of whoever runs them.
os.environ["URNA_CONFIG_DIR"] = tempfile.mkdtemp(prefix="urna-preferencias-")
atexit.register(shutil.rmtree, os.environ["URNA_CONFIG_DIR"], True)


@pytest.fixture(autouse=True)
def spanish():
    """The tests read the messages in Spanish, whatever the language of the computer that runs them."""
    from urna_padrones import i18n

    i18n.set_language("es")
    yield
    i18n.set_language(None)
