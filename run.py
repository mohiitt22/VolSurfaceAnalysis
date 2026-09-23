"""Entry point.

    python run.py --phase 1     # data dictionary / quality report only
    python run.py --phase all   # full research + frozen 11 Sep 2026 test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import DEFAULT
from src.pipeline import run_all, setup_logging
from src.reporting.phase1 import run_phase1


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", default="all", choices=["1", "all"])
    args = p.parse_args()
    setup_logging()
    if args.phase == "1":
        run_phase1(DEFAULT)
        return
    run_phase1(DEFAULT)
    run_all(DEFAULT)


if __name__ == "__main__":
    main()
