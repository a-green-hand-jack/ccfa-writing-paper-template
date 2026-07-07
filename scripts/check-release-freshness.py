#!/usr/bin/env python3
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_harness_checks import run

raise SystemExit(run("release_freshness"))
