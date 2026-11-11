"""Build the packaged roll reader for the system this runs on, check it and archive it.

    uv sync --locked --managed-python --no-editable --group build
    uv run --no-sync python packaging/build.py            # dist/urna-abierta-lector-<os>-<arch>/
    uv run --no-sync python packaging/build.py --self-test --archive

For Alpine and the other Linux with musl, the Python that builds it is prepared by packaging/alpine.sh.

--self-test runs the built program's own check with every proxy pointing at a dead port and an
empty temp folder of its own. It fails if anything in the bundle changed (a downloaded model would
land there) or if onnxruntime's telemetry left its .ses file in that folder. --start-time
measures how long the program takes to print its address. --archive writes the file to publish
and its SHA-256: a .zip on Windows and macOS (the .app, made with ditto), a .tar.gz on Linux.

URNA_VERSION names the version (by default 0.0.0) and URNA_SOURCE_URL the source code address
written in the notices. The build uses a fixed PYTHONHASHSEED and SOURCE_DATE_EPOCH (the time of
the last commit), and the Linux and Windows archives fixed dates and owners. On Linux, building
the same commit twice gives the same archive. The macOS zip is not reproducible: ditto keeps the
time each file was built.
"""

import argparse
import gzip
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"
PROGRAM = "urna-abierta-lector"
APP = "Urna Abierta Lector.app"
MODEL = "PP-OCRv6_rec_small.onnx"
DEAD_PROXY = "http://127.0.0.1:9"
# What onnxruntime's telemetry leaves in the temp folder when it is on.
TELEMETRY_FILE = ".ses"
# LSMinimumSystemVersion in lector.spec.
MACOS_MINIMUM = (14, 0)


def musl() -> bool:
    """Alpine and the other Linux with musl instead of glibc (packaging/alpine.sh builds there)."""
    return sys.platform.startswith("linux") and any(Path("/lib").glob("ld-musl-*.so.1"))


def system() -> tuple[str, str]:
    name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    return name, arch + ("-musl" if musl() else "")


def bundle_name() -> str:
    name, arch = system()
    return f"{PROGRAM}-{name}-{arch}"


def bundle_folder() -> Path:
    """The folder that gets published: the .app on macOS, the program's folder elsewhere."""
    return DIST / APP if sys.platform == "darwin" else DIST / bundle_name()


def program() -> Path:
    if sys.platform == "darwin":
        return DIST / APP / "Contents" / "MacOS" / PROGRAM
    return bundle_folder() / (PROGRAM + (".exe" if sys.platform == "win32" else ""))


def source_date_epoch() -> str:
    if os.environ.get("SOURCE_DATE_EPOCH"):
        return os.environ["SOURCE_DATE_EPOCH"]
    try:
        done = subprocess.run(
            ["git", "log", "-1", "--format=%ct"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return done.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "315532800"  # 1980-01-01, the earliest date a zip file can hold


def build() -> None:
    env = {
        **os.environ,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": source_date_epoch(),
        "URNA_LECTOR_NAME": bundle_name(),
        "URNA_VERSION": os.environ.get("URNA_VERSION", "0.0.0"),
    }
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--distpath", str(DIST), "--workpath", str(WORK), str(HERE / "lector.spec"),
    ]  # fmt: skip
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def files_of(folder: Path) -> dict[str, int]:
    return {p.relative_to(folder).as_posix(): p.lstat().st_size for p in sorted(folder.rglob("*")) if not p.is_dir()}


def check() -> None:
    """What must and must not be in the bundle."""
    files = files_of(bundle_folder())
    names = [Path(name).name for name in files]
    models = [name for name in files if name.lower().endswith(".onnx")]
    problems = []
    if [Path(m).name for m in models] != [MODEL]:
        problems.append(f"models: {models}")
    if any(n.lower().startswith("opencv_videoio_ffmpeg") for n in names):
        problems.append("OpenCV's FFmpeg plugin is in the bundle")
    if any(n.startswith(("_tkinter", "libtk", "libtcl", "tcl8", "tk8")) for n in names):
        problems.append("Tcl/Tk is in the bundle")
    for needed in ("THIRD_PARTY_NOTICES.txt", "LICENSE.txt", "index.html", "muestra.png", "ocr_sample.png"):
        if needed not in names:
            problems.append(f"missing {needed}")
    if not program().is_file():
        problems.append(f"missing {program()}")
    if problems:
        raise SystemExit("The bundle is not right:\n  " + "\n  ".join(problems))
    size = sum(files.values())
    print(f"bundle: {bundle_folder().name}, {len(files)} files, {size / 1e6:.1f} MB unpacked")
    if sys.platform.startswith("linux") and not musl() and shutil.which("readelf"):
        print(f"bundle: needs glibc {glibc_floor(bundle_folder())} or newer")
    if sys.platform == "darwin":
        floor = macos_floor(bundle_folder())
        print(f"bundle: needs macOS {floor[0]}.{floor[1]} or newer")
        if floor > MACOS_MINIMUM:
            raise SystemExit(f"lector.spec says macOS {MACOS_MINIMUM[0]}.{MACOS_MINIMUM[1]}: update it and the README")


def macos_floor(folder: Path) -> tuple[int, int]:
    """The newest macOS version that any library or program in the folder was built for."""
    newest = (0, 0)
    magics = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
    for path in folder.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with open(path, "rb") as file:
            if file.read(4) not in magics:
                continue
        lines = subprocess.run(
            ["otool", "-l", str(path)], capture_output=True, text=True, check=False
        ).stdout.splitlines()
        for number, line in enumerate(lines):
            words = line.split()
            # LC_BUILD_VERSION says "minos 14.0"; the older LC_VERSION_MIN_MACOSX says "version 10.13".
            older = words[:1] == ["version"] and any(
                "LC_VERSION_MIN_MACOSX" in x for x in lines[max(0, number - 3) : number]
            )
            if len(words) == 2 and (words[0] == "minos" or older):
                parts = (words[1].split(".") + ["0"])[:2]
                if all(p.isdigit() for p in parts):
                    newest = max(newest, (int(parts[0]), int(parts[1])))
    return newest


def glibc_floor(folder: Path) -> str:
    """The newest glibc symbol version that any library or program in the folder asks for."""
    newest = (0, 0)
    for path in folder.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with open(path, "rb") as file:
            if file.read(4) != b"\x7fELF":
                continue
        done = subprocess.run(["readelf", "-V", "--wide", str(path)], capture_output=True, text=True, check=False)
        for word in done.stdout.split():
            if word.startswith("GLIBC_2."):
                parts = word.removeprefix("GLIBC_").split(".")
                if all(p.isdigit() for p in parts):
                    newest = max(newest, (int(parts[0]), int(parts[1])))
    return f"{newest[0]}.{newest[1]}"


def without_network_env() -> dict[str, str]:
    """Every proxy variable pointing at a port where nothing listens: any download fails at once."""
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[name] = DEAD_PROXY
    env.pop("URNA_PADRONES_MODELO", None)
    return env


def with_temp_folder(env: dict[str, str], folder: Path) -> dict[str, str]:
    """The environment with the temp folder variables of every system pointing at folder."""
    return {**env, "TMPDIR": str(folder), "TMP": str(folder), "TEMP": str(folder)}


def check_temp_folder(folder: Path, what: str) -> None:
    """Fail if onnxruntime's telemetry left its file in the program's temp folder; say what else is left."""
    left = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))
    telemetry = [name for name in left if Path(name).name.endswith(TELEMETRY_FILE)]
    if telemetry:
        raise SystemExit(f"{what}: onnxruntime's telemetry is on, it left {telemetry} in the temp folder")
    if left:
        print(f"{what}: left in its temp folder: {left}")


def self_test() -> None:
    before = files_of(bundle_folder())
    for attempt in ("first", "second"):
        temp = Path(tempfile.mkdtemp(prefix="urna-lector-self-test-"))
        try:
            start = time.monotonic()
            done = subprocess.run(
                [str(program()), "--self-test"],
                env=with_temp_folder(without_network_env(), temp),
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            seconds = time.monotonic() - start
            if (done.returncode, done.stdout) != (0, "ok\n"):
                raise SystemExit(f"self test failed ({done.returncode}):\n{done.stdout}\n{done.stderr}")
            check_temp_folder(temp, "self test")
        finally:
            shutil.rmtree(temp, ignore_errors=True)
        print(f"self test: ok, {attempt} run {seconds:.1f} s, no telemetry file")
    after = files_of(bundle_folder())
    if before != after:
        changed = sorted(set(before.items()) ^ set(after.items()))
        raise SystemExit(f"the self test changed the bundle (a download?): {changed}")
    print("self test: nothing in the bundle changed, no model was downloaded")


def start_time() -> None:
    """Seconds until the program prints its address, then it is closed through its own screen's route."""
    temp = Path(tempfile.mkdtemp(prefix="urna-lector-start-"))
    env = with_temp_folder({**without_network_env(), "URNA_NO_BROWSER": "1"}, temp)
    start = time.monotonic()
    process = subprocess.Popen([str(program()), "--no-browser"], env=env, stdout=subprocess.PIPE, text=True)
    try:
        url = process.stdout.readline().strip()
        seconds = time.monotonic() - start
        if not url.startswith("http://127.0.0.1:"):
            raise SystemExit(f"the program did not print its address: {url!r}")
        request = urllib.request.Request(url + "api/quit", data=b"{}", method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=30) as answer:
            answer.read()
        process.wait(timeout=30)
        check_temp_folder(temp, "start")
    finally:
        if process.poll() is None:
            process.kill()
        shutil.rmtree(temp, ignore_errors=True)
    print(f"start: address after {seconds:.1f} s, closed with code {process.returncode}")


def deterministic_entries(folder: Path) -> list[Path]:
    return [folder, *sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix())]


def archive() -> Path:
    epoch = int(source_date_epoch())
    name = bundle_name()
    if sys.platform == "darwin":
        target = DIST / f"{name}.zip"
        target.unlink(missing_ok=True)
        # ditto keeps the symbolic links and the signature of the .app, which zipfile would lose.
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle_folder()), str(target)], check=True)
    elif sys.platform == "win32":
        target = DIST / f"{name}.zip"
        stamp = time.gmtime(max(epoch, 315532800))[:6]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
            for path in deterministic_entries(bundle_folder())[1:]:
                arcname = f"{name}/{path.relative_to(bundle_folder()).as_posix()}"
                if path.is_dir():
                    out.writestr(zipfile.ZipInfo(arcname + "/", stamp), b"")
                    continue
                info = zipfile.ZipInfo(arcname, stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                out.writestr(info, path.read_bytes())
    else:
        target = DIST / f"{name}.tar.gz"

        def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = epoch
            if info.isfile() or info.isdir():
                info.mode = 0o755 if info.isdir() or info.mode & 0o111 else 0o644
            return info

        folder = bundle_folder()
        with (
            open(target, "wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as packed,
            tarfile.open(fileobj=packed, mode="w", format=tarfile.PAX_FORMAT) as out,
        ):
            for path in deterministic_entries(folder):
                arcname = name if path == folder else f"{name}/{path.relative_to(folder).as_posix()}"
                out.add(path, arcname=arcname, recursive=False, filter=normalize)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    sums = target.with_name(target.name + ".sha256")
    sums.write_text(f"{digest}  {target.name}\n", encoding="ascii", newline="\n")
    print(f"archive: {target.name}, {target.stat().st_size / 1e6:.1f} MB, sha256 {digest}")
    # For the release workflow: which files to attest and upload.
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"archive={target.as_posix()}\nsums={sums.as_posix()}\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the packaged roll reader for this system.")
    parser.add_argument("--no-build", action="store_true", help="use the bundle already in dist/")
    parser.add_argument("--self-test", action="store_true", help="run the program's own check, without network")
    parser.add_argument("--start-time", action="store_true", help="measure how long it takes to print its address")
    parser.add_argument("--archive", action="store_true", help="write the archive to publish and its SHA-256")
    args = parser.parse_args()
    if not args.no_build:
        if sys.platform == "darwin":
            shutil.rmtree(DIST / APP, ignore_errors=True)
        build()
    check()
    if args.self_test:
        self_test()
    if args.start_time:
        start_time()
    if args.archive:
        archive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
