"""The model is local: it ships with the program and nothing is fetched or sent."""

import json
import os
import socket
import subprocess
import sys
import threading
from importlib import resources

import pytest
from rapidocr.utils.download_file import DownloadFile

from urna_padrones import ocr


def no_network(*args, **kwargs):
    raise AssertionError("se intentó usar la red / the network was used")


@pytest.fixture
def offline(monkeypatch):
    """Any connection or name lookup fails, and the engine has to be created again."""
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(ocr, "_local", threading.local())
    monkeypatch.delenv(ocr.MODEL_VARIABLE, raising=False)


def test_the_offline_guard_works(offline):
    with pytest.raises(AssertionError):
        socket.create_connection(("example.org", 443))


def test_creates_the_engine_and_reads_a_cell_without_network(offline):
    cells = ocr.sample_cells()
    text, confidence = ocr.read_cell(cells[2])
    assert text == ocr.SAMPLE_TEXT[2]
    assert confidence > 0.9


def test_the_model_ships_inside_the_rapidocr_package():
    model = ocr.bundled_model()
    assert model.is_file()
    assert model.parent.name == "models" and model.parent.parent.name == "rapidocr"


def test_the_engine_uses_the_bundled_model_explicitly(monkeypatch):
    monkeypatch.delenv(ocr.MODEL_VARIABLE, raising=False)
    assert ocr.create_engine().cfg.Rec.model_path == str(ocr.bundled_model())


def test_another_model_can_be_chosen(monkeypatch, tmp_path):
    link = tmp_path / "otro-modelo.onnx"
    try:
        os.symlink(ocr.bundled_model(), link)
    except OSError:
        pytest.skip("no se pueden crear enlaces en este sistema")
    monkeypatch.setenv(ocr.MODEL_VARIABLE, str(link))
    assert ocr.model_path() == link
    assert ocr.create_engine().cfg.Rec.model_path == str(link)


def test_a_missing_model_is_an_error_not_a_download(monkeypatch, tmp_path):
    monkeypatch.setenv(ocr.MODEL_VARIABLE, str(tmp_path / "no-existe.onnx"))
    with pytest.raises(FileNotFoundError):
        ocr.create_engine()


def test_the_downloader_refuses():
    with pytest.raises(RuntimeError):
        DownloadFile.run(None)


def test_self_test_reads_the_bundled_sample(offline):
    assert ocr.self_test()


def test_self_test_fails_without_a_model(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_local", threading.local())
    monkeypatch.setenv(ocr.MODEL_VARIABLE, str(tmp_path / "no-existe.onnx"))
    assert not ocr.self_test()


TELEMETRY_PROBE = """
import json, os, sys, threading, time

def inet_sockets():
    found = set()
    for name in ("tcp", "tcp6", "udp", "udp6"):
        try:
            with open(f"/proc/self/net/{name}") as table:
                next(table)
                found.update(line.split()[9] for line in table)
        except OSError:
            pass
    return found

def my_sockets():
    inodes = set()
    for fd in os.listdir("/proc/self/fd"):
        try:
            link = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            continue
        if link.startswith("socket:["):
            inodes.add(link[8:-1])
    return inodes

seen, done = set(), threading.Event()

def watch():
    while not done.is_set():
        mine = my_sockets()
        if mine:
            seen.update(mine & inet_sockets())
        time.sleep(0.002)

watching = sys.platform.startswith("linux")
if watching:
    threading.Thread(target=watch, daemon=True).start()
from urna_padrones import ocr
ok = ocr.self_test()
time.sleep(0.5)
done.set()
print(json.dumps({"ok": ok, "watching": watching, "inet": len(seen)}))
"""


def test_the_reading_engine_sends_nothing_and_leaves_nothing(tmp_path):
    """onnxruntime's own telemetry stays off: no connection and no .ses file in the temp folder."""
    env = {k: v for k, v in os.environ.items() if k not in ("ORT_DISABLE_TELEMETRY", ocr.MODEL_VARIABLE)}
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(tmp_path)
    done = subprocess.run(
        [sys.executable, "-c", TELEMETRY_PROBE], env=env, capture_output=True, text=True, timeout=300, check=True
    )
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["ok"]
    assert not (tmp_path / ".ses").exists()
    assert list(tmp_path.iterdir()) == []
    if result["watching"]:
        assert result["inet"] == 0


def test_the_sample_image_is_small():
    assert len((resources.files("urna_padrones") / ocr.SAMPLE_IMAGE).read_bytes()) < 20_000
