"""Build only the staged protected modules; never edit repository Python source."""
import argparse
import os
import shutil
from pathlib import Path
from setuptools import Extension, setup
from Cython.Build import cythonize
from Cython.Compiler import Options
from release_policy import NATIVE_MODULES

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    backend, work = Path(args.backend).resolve(), Path(args.work_dir).resolve()
    if work.name != "native" or backend != work.parent / "stage/backend":
        raise RuntimeError("Compile a staging copy, never the source backend")
    work.mkdir(parents=True, exist_ok=True)
    (work / "input").mkdir(exist_ok=True)
    extensions = []
    for module in NATIVE_MODULES:
        relative = Path(*module.split(".")).with_suffix(".py")
        target = work / "input" / relative.name
        shutil.copy2(backend / relative, target)
        extensions.append(Extension(module, [str(Path("input") / relative.name)]))
    os.chdir(work)
    Options.docstrings = False
    setup(name="scada-protected", script_args=["build_ext", "--build-lib", str(backend),
          "--build-temp", "obj"],
          ext_modules=cythonize(extensions,
              build_dir="cython", force=True,
              compiler_directives={"language_level": 3, "annotation_typing": False,
                                   "binding": True, "embedsignature": False}))
