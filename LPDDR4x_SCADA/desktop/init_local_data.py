"""Create private, hardware-disabled development data without storing cfg in Git."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.localdata import init_mock_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[1] / "local_data"))
    args = parser.parse_args()
    print(init_mock_data(args.data_dir))
