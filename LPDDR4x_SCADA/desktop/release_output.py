"""Publish a verified release to the fixed build directory without archiving it."""
from pathlib import Path
import shutil

EXE = "LPDDR4x_SCADA_PYD.exe"
PROGRAM_DIRS = ("_internal", "frontend_dist")
INTERNAL_RELEASE_FILES = frozenset({"BUILD_REPORT.json"})
SOURCE_SUFFIXES = frozenset({
    ".py", ".pyx", ".pxd", ".c", ".h", ".cpp", ".ts", ".tsx", ".map",
    ".pdb", ".obj", ".spec", ".ps1", ".bat", ".cmd",
})


def check_customer_bundle(bundle: Path) -> None:
    """Reject engineering inputs before changing an existing release."""
    forbidden = []
    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle)
        if relative.parts[0] in {"backend", "frontend", "desktop", ".git", "node_modules", ".venv"}:
            forbidden.append(relative.as_posix())
        elif path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            forbidden.append(relative.as_posix())
    if forbidden:
        raise ValueError("Engineering files must not enter customer release:\n" + "\n".join(forbidden))


def release_output(repo: Path, requested=None) -> Path:
    repo = repo.resolve()
    output = Path(requested).absolute() if requested else repo / "build"
    if output.is_symlink() or output.is_junction() or output.resolve() != repo / "build":
        raise ValueError("Release output must be the repository build directory")
    if output.exists():
        if not output.is_dir():
            raise ValueError("Release output must be a directory")
        if any(output.iterdir()) and not ((output / EXE).is_file() and
                                         all((output / name).is_dir() for name in PROGRAM_DIRS)):
            raise ValueError("Existing build directory is not a recognized release")
        if any(p.is_symlink() or p.is_junction() for p in output.rglob("*")):
            raise ValueError("Release output must not contain linked paths")
    return output


def publish_release(bundle: Path, repo: Path, requested=None) -> Path:
    """Copy the verified package, remove stale program files, keep runtime logs."""
    output = release_output(repo, requested)
    bundle = bundle.resolve()
    if not bundle.is_relative_to(repo.resolve() / "desktop" / "build"):
        raise ValueError("Release bundle must be inside desktop/build")
    if not (bundle / EXE).is_file() or not all((bundle / name).is_dir() for name in PROGRAM_DIRS):
        raise ValueError("Release bundle is incomplete")
    check_customer_bundle(bundle)
    for name in INTERNAL_RELEASE_FILES:
        if (output / name).exists() and not (output / name).is_file():
            raise ValueError("Internal release report path must be a file")
    stale = []
    for name in PROGRAM_DIRS:
        stale.extend(p for p in (output / name).rglob("*")
                     if p.is_file() and not (bundle / p.relative_to(output)).is_file())
    output.mkdir(exist_ok=True)
    # Fail early when Windows still holds the executable; do not remove files first.
    shutil.copy2(bundle / EXE, output / EXE)
    shutil.copytree(bundle, output, dirs_exist_ok=True,
                    ignore=lambda directory, names: set(names) & INTERNAL_RELEASE_FILES
                    if Path(directory) == bundle else set())
    # Older releases shipped this internal evidence; remove only these exact files.
    for name in INTERNAL_RELEASE_FILES:
        (output / name).unlink(missing_ok=True)
    for path in stale:
        path.unlink()
    for name in PROGRAM_DIRS:
        for path in sorted((output / name).rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return output
