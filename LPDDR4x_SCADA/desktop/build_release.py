"""One source-to-release pipeline. All outputs are private and excluded from Git."""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

from audit_source import audit
from stage_payload import stage_payload
from release_policy import NATIVE_MODULES
from release_output import release_output, publish_release

REPO = Path(__file__).resolve().parents[1]


def run(command, cwd, log, env=None):
    print("RUN:", " ".join(map(str, command)), flush=True)
    with log.open("w", encoding="utf-8") as out:
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                                stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(encoding="utf-8", errors="replace")[-9000:])
        raise RuntimeError(f"Command failed ({result.returncode}): {log}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--mode", choices=("field", "mock"), default="field")
    parser.add_argument("--output")
    parser.add_argument("--qa-key-file", help="可选管理端密钥，用于真实跨到期验收，不会复制入运行包")
    args = parser.parse_args()
    if sys.platform != "win32" or sysconfig.get_platform() != "win-amd64" or sysconfig.get_config_var("Py_GIL_DISABLED"):
        raise RuntimeError("Validated build target: Windows x64, CPython with GIL")
    count = audit(REPO)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    work = REPO / "desktop/build" / ("release_" + stamp)
    stage = work / "stage"
    work.mkdir(parents=True, exist_ok=False)
    output = release_output(REPO, args.output)
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO).decode("utf-8").split("\0")
    hashes = {}
    for name in tracked:
        if not name or not name.startswith(("backend/", "desktop/", "frontend/")):
            continue
        path = REPO / name
        if not path.is_file():
            raise FileNotFoundError(f"Tracked input missing: {name}")
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (work / "source-sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    # Preflight private data before costly compilation. Copies go only into the private work dir.
    preview = work / "payload_preflight"
    front_stub = work / "front_stub"
    front_stub.mkdir()
    (front_stub / "index.html").write_text("preflight", encoding="utf-8")
    payload = stage_payload(Path(args.data_dir), preview, front_stub, args.mode)
    run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
        stage / "desktop", work / "release-tests.log", env)
    run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
        stage / "backend", work / "source-tests.log", env)
    npm = shutil.which("npm.cmd")
    if not npm:
        raise RuntimeError("Node.js/npm missing")
    run([npm, "ci", "--no-audit", "--no-fund"], stage / "frontend", work / "npm-ci.log", env)
    for command, name in (([npm, "test"], "frontend-tests.log"),
                          (["node", "scripts/test-manual-state.mjs"], "manual-state-tests.log"),
                          ([npm, "run", "build"], "frontend-build.log")):
        run(command, stage / "frontend", work / name, env)
    run([sys.executable, "-B", str(stage / "desktop/build_pyd.py"), "--backend", str(stage / "backend"),
         "--work-dir", str(work / "native")], work, work / "cython-build.log", env)
    # Remove only known staging copies. Source modules remain in the repository.
    for module in NATIVE_MODULES:
        source = stage / "backend" / Path(*module.split(".")).with_suffix(".py")
        assert source.is_relative_to(work) and source.is_file()
        source.unlink()
    run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
        stage / "backend", work / "compiled-tests.log", env)
    run([sys.executable, "-B", "-c", "import app.protocol as p; assert p.__file__.endswith('.pyd'); assert p.__doc__ is None; assert p.HsgCodec.__doc__ is None; assert p.HsgCodec.encode.__doc__ is None; assert p.HsgCodec.decode.__doc__ is None; print(p.__file__)"],
        stage / "backend", work / "docstrings.log", env)
    env["SLT_BUILD_STAGE"] = str(stage)
    run([sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(work / "dist"),
         "--workpath", str(work / "pyinstaller"), str(stage / "desktop/LPDDR4x_SCADA_Desktop.spec")],
        REPO / "desktop", work / "pyinstaller.log", env)
    bundle = work / "dist/LPDDR4x_SCADA_PYD"
    payload = stage_payload(Path(args.data_dir), bundle, stage / "frontend/dist", args.mode)
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(bundle / "LPDDR4x_SCADA_PYD.exe"))
    pyz = archive.open_embedded_archive(next(name for name in archive.toc if name.endswith(".pyz")))
    for module in NATIVE_MODULES:
        assert module not in pyz.toc, f"Protected bytecode leaked into PYZ: {module}"
    assert not any(name.startswith("licensing_tools") for name in pyz.toc), "Issuer tool entered customer bundle"
    from release_policy import EXCLUDES
    assert not any(name in pyz.toc for name in EXCLUDES)
    code = pyz.extract("app.main")
    source_doc = ast.get_docstring(ast.parse((stage / "backend/app/main.py").read_text(encoding="utf-8-sig")))
    assert source_doc and source_doc not in code.co_consts, "Python module docstring was not stripped"
    forbidden = [p for p in bundle.rglob("*") if p.is_file() and p.suffix in (".py", ".pyx", ".c")]
    assert not forbidden, forbidden
    native = list((bundle / "_internal/app").glob("protocol*.pyd"))
    assert len(native) == 1
    protected = {}
    for module in NATIVE_MODULES:
        files = list((bundle / "_internal/app").glob(module.split(".")[-1] + "*.pyd"))
        assert len(files) == 1, module
        protected[module] = hashlib.sha256(files[0].read_bytes()).hexdigest()
    report = {"source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip(),
              "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO)),
              "tracked_files": count, "python": sys.version, "extension_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
              "pyd_sha256": hashlib.sha256(native[0].read_bytes()).hexdigest(),
              "protocol_in_pyz": False, "protected_modules": protected,
              "issuer_in_customer_bundle": False, "docstrings_stripped": True, "excludes": EXCLUDES,
              "payload": payload, "work_dir": str(work), "output": str(output), "smoke_verified": False}
    report_path = work / "BUILD_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle / "README.txt").write_text("Run LPDDR4x_SCADA_PYD.exe. Keep the complete folder, including _internal, frontend_dist, products and strategies.\n", encoding="utf-8")
    # Verify the candidate first; a failed build or smoke must leave build untouched.
    run([sys.executable, "-B", str(REPO / "desktop/verify_release.py"), "--package", str(bundle),
         "--build-report", str(report_path)] +
        (["--qa-key-file", args.qa_key_file] if args.qa_key_file else []),
        REPO, work / "smoke.log", env)
    report.update(json.loads(report_path.read_text(encoding="utf-8")))
    publish_release(bundle, REPO, output)
    report["output_sha256"] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in output.rglob("*") if p.is_file()}
    (work / "build-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "work": str(work), "pyd_sha256": report["pyd_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
