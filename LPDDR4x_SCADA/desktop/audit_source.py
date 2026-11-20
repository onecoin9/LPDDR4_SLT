"""Fail closed if Git tracks private configuration or compiled deliverables."""
from pathlib import PurePosixPath, Path
import subprocess
import argparse
import sys

SUFFIXES = {".cfg", ".exe", ".dll", ".pyd", ".pyc", ".pyo", ".so", ".obj", ".lib",
            ".pdb", ".pcap", ".pcapng", ".xlsx", ".pptx", ".log", ".lic", ".dpapi"}
PRIVATE = ("backend/products/", "backend/strategies/", "backend/manual_logs/",
           "backend/records/", "backend/_pyd_poc/", "local_data/", "bulid/", "build/",
           "desktop/build/", "desktop/dist/", "frontend/dist/", "SCADA_", "memtester_slides/", "mtk_memtester_src/")


def check_files(names):
    bad = []
    for name in names:
        p = PurePosixPath(name)
        if (p.suffix.lower() in SUFFIXES or name.startswith(PRIVATE)
                or (p.parts and p.parts[0].startswith("bulid_"))
                or "node_modules" in p.parts or "__pycache__" in p.parts
                or name == "backend/config.yaml" or name.startswith("backend/config.") and name.endswith(".yaml")
                or name.startswith("backend/session_settings") and name.endswith(".json")
                or name in {"backend/machine_settings.json", "backend/runtime_policy.json", "backend/settings.json",
                            "backend/.settings.active", "backend/handler_settings.json"} or p.name.startswith(".env")
                or p.name.endswith(".private.key") or "private" in p.parts and "licensing_tools" in p.parts):
            bad.append(name)
    if bad:
        raise RuntimeError("Forbidden tracked files:\n" + "\n".join(bad))


def audit(repo, revision=None):
    command = ["git", "ls-files", "-z"] if revision is None else ["git", "ls-tree", "-r", "--name-only", "-z", revision]
    files = subprocess.check_output(command, cwd=repo).decode("utf-8").split("\0")
    check_files([name for name in files if name])
    return len([name for name in files if name])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', action='store_true')
    parser.add_argument('--push-refs', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    print(f"Source-only Git index: {audit(repo)} files")
    if args.head:
        print(f"Source-only HEAD: {audit(repo, 'HEAD')} files")
    if args.push_refs:
        revisions = {line.split()[1] for line in sys.stdin if len(line.split()) == 4}
        for revision in sorted(revisions):
            if set(revision) != {'0'}:
                print(f"Source-only push {revision[:12]}: {audit(repo, revision)} files")
