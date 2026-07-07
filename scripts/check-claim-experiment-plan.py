#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_harness_checks import run

raise SystemExit(run("claim_experiment_plan"))
