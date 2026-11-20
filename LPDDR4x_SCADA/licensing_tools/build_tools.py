"""Build separate customer ClientIDTool and owner LicenseIssuer; never copy keys."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--native-dir", required=True, help="包含正式 license_machine.pyd 的目录")
    p.add_argument("--output", help="主仓内英文 bulid* 目录；禁止覆盖")
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(a.output).resolve() if a.output else repo / ("bulid_license_tools_" + stamp)
    if output.exists() or output.parent != repo or not output.name.startswith("bulid") or not output.name.isascii():
        raise ValueError("Output must be a new English bulid* directory inside repository")
    natives = list(Path(a.native_dir).glob("license_machine*.pyd"))
    if len(natives) != 1:
        raise ValueError("Exactly one compiled machine module is required")
    # 容器模块双份（app 编译进 pyd / tools 随源进 exe）必须逐字节一致
    container_a = repo / "backend/app/license_container.py"
    container_b = repo / "licensing_tools/license_container.py"
    if container_a.read_bytes() != container_b.read_bytes():
        raise ValueError("license_container.py app/tools copies differ; sync them first")
    work = repo / "desktop/build" / ("license_tools_" + stamp)
    work.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
    report = {}
    from PyInstaller.archive.readers import CArchiveReader
    for name, entry, sources in (
        ("ClientIDTool", "client_id_tool.py", ["__init__.py", "client_request.py", "license_container.py", "client_id_tool.py"]),
        ("LicenseIssuer", "issuer_tool.py", ["__init__.py", "client_request.py", "license_container.py", "private_key.py", "issue_license.py", "issuer_tool.py"]),
    ):
        stage = work / name
        (stage / "licensing_tools").mkdir(parents=True)
        for source in sources:
            shutil.copy2(repo / "licensing_tools" / source, stage / "licensing_tools" / source)
        extra = []
        if name == "ClientIDTool":
            (stage / "app").mkdir()
            (stage / "app/__init__.py").write_text("", encoding="utf-8")
            shutil.copy2(natives[0], stage / "app" / natives[0].name)
            extra = ["--hidden-import", "app.license_machine", "--hidden-import", "winreg", "--hidden-import", "hashlib", "--hidden-import", "subprocess", "--hidden-import", "re"]
        command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--optimize", "2", "--noupx", "--name", name,
                   "--paths", str(stage), "--distpath", str(work / "dist"), "--workpath", str(work / "pyinstaller" / name), "--specpath", str(work),
                   "--exclude-module", "pytest", "--exclude-module", "Cython", "--exclude-module", "webview", *extra, str(stage / "licensing_tools" / entry)]
        with (work / (name + "-build.log")).open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=stage, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        bundle = work / "dist" / name
        archive = CArchiveReader(str(bundle / (name + ".exe")))
        pyz = archive.open_embedded_archive(next(x for x in archive.toc if x.endswith(".pyz")))
        if name == "ClientIDTool":
            for module in ("licensing_tools.private_key", "licensing_tools.issue_license", "licensing_tools.issuer_tool", "app.license_machine"):
                assert module not in pyz.toc, f"Customer request tool leaked protected/owner module: {module}"
        assert not any(f.name.endswith(".private.key") or f.suffix in (".py", ".c", ".pyx") for f in bundle.rglob("*") if f.is_file())
        shutil.copytree(bundle, output / name)
        report[name] = {"exeSha256": hashlib.sha256((bundle / (name + ".exe")).read_bytes()).hexdigest(), "privateKeyIncluded": False}
    (output / "BUILD_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "work": str(work)}))


if __name__ == "__main__":
    main()
