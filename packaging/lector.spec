# PyInstaller spec of the packaged roll reader: one folder, built on the system it is for.
# Run it through build.py, which names the output and sets the environment for a reproducible build:
#     uv run --group build python packaging/build.py
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

HERE = Path(SPECPATH)
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import notices  # noqa: E402
from build import MACOS_MINIMUM  # noqa: E402

from urna_padrones.ocr import BUNDLED_MODEL, bundled_model  # noqa: E402

NAME = os.environ.get("URNA_LECTOR_NAME", "urna-abierta-lector")
VERSION = os.environ.get("URNA_VERSION", "0.0.0")
SOURCE_URL = os.environ.get("URNA_SOURCE_URL", "")
MACOS = sys.platform == "darwin"
WINDOWS = sys.platform == "win32"
APP_NAME = "Urna Abierta Lector"
PROGRAM = "urna-abierta-lector"

# rapidocr's configuration, and of its models only the recognition model the reader uses.
datas = collect_data_files("rapidocr", excludes=["models/*"])
datas.append((str(bundled_model()), "rapidocr/models"))
# The reader's screens, its font with its license, and the two sample images of the self test.
datas += collect_data_files("urna_padrones", excludes=["**/README.md"])

a = Analysis(
    [str(HERE / "launcher.py")],
    datas=datas,
    excludes=[
        # Not used, and large: a GUI toolkit, onnxruntime's optional symbolic tools, other engines.
        "tkinter",
        "_tkinter",
        "sympy",
        "mpmath",
        "IPython",
        "matplotlib",
        "torch",
        "paddle",
        "openvino",
        "tensorrt",
        "MNN",
        "pytest",
    ],
    optimize=0,
)

# OpenCV loads FFmpeg on Windows as a separate video plugin, which reading pages never needs.
left_out = ("opencv_videoio_ffmpeg",)
if sys.platform.startswith("linux"):
    # The C++ runtime of the build machine would ask for its glibc (2.35 on Ubuntu 22.04). Every
    # Linux with a desktop has one, and the wheels only need what glibc 2.28 systems have.
    left_out += ("libstdc++.so", "libgcc_s.so")
a.binaries = [entry for entry in a.binaries if not Path(entry[0]).name.lower().startswith(left_out)]
ffmpeg = any(Path(dest).name.startswith(("libavcodec", "avcodec")) for dest, _, _ in a.binaries)

models = [dest for dest, _, _ in a.datas if dest.lower().endswith(".onnx")]
if [Path(dest).name for dest in models] != [BUNDLED_MODEL]:
    raise SystemExit(f"Expected only {BUNDLED_MODEL} in the bundle, found: {models}")

# The notices list what was actually collected.
top_level = {name.split(".")[0] for name, _, _ in a.pure}
top_level |= {Path(dest).parts[0] for dest, _, _ in a.binaries + a.datas}
# Python's own extension modules: in lib-dynload/ on Linux and macOS, next to the program on Windows.
extension_modules = {
    Path(dest).name.split(".")[0]
    for dest, _, _ in a.binaries
    if len(Path(dest).parts) == 1 or Path(dest).parts[0] == "lib-dynload"
}
written = notices.write_notices(
    Path(workpath) / "notices",
    notices.bundled_distributions(top_level),
    version=VERSION,
    source_url=SOURCE_URL,
    ffmpeg=ffmpeg,
    extension_modules=extension_modules,
)
for path in written:
    a.datas.append((path.relative_to(Path(workpath) / "notices").as_posix(), str(path), "DATA"))
a.datas.append(("LICENSE.txt", str(ROOT / "LICENSE"), "DATA"))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=PROGRAM,
    # Windows and Linux keep a console that says where the reader is; closing it closes the reader.
    # On macOS the program is an app without a window: it opens the browser and nothing else.
    console=not MACOS,
    icon="NONE" if WINDOWS else None,
    debug=False,
    strip=False,
    upx=False,
    contents_directory="_internal",
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)

if MACOS:
    short_version = VERSION.lstrip("v").split("-")[0] or "0.0.0"
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="org.urnaabierta.lector",
        version=short_version,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleVersion": short_version,
            "CFBundleDevelopmentRegion": "es",
            # No icon in the Dock: the reader has no window of its own, its screens are in the browser.
            "LSUIElement": True,
            # onnxruntime and OpenCV need macOS 14 on both kinds of Mac; build.py checks it.
            "LSMinimumSystemVersion": "%d.%d" % MACOS_MINIMUM,
            "NSHumanReadableCopyright": "AGPL-3.0-or-later",
        },
    )
