"""Entry point for hosts that expect ``app.py`` at the repository root."""

from pathlib import Path
from runpy import run_path

APP = Path(__file__).parent / "src" / "cardiac_capacity_planner" / "app.py"
run_path(str(APP), run_name="__main__")
