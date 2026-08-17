import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.prosperity_io import DataRoot  # noqa: E402
from research.style import use_style  # noqa: E402


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="data", type=Path,
                   help="folder holding ROUND_1 ... ROUND_5 from the Prosperity data capsules")
    p.add_argument("--out", default="figures", type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    use_style()
    return DataRoot(a.data_root), a.out
