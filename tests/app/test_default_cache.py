"""The default-run cache must equal a fresh run and must never go stale silently."""

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

from cardiac_capacity_planner import default_cache

_spec = importlib.util.spec_from_file_location(
    "build_default_cache", Path(__file__).resolve().parents[2] / "scripts" / "build_default_cache.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["build_default_cache"] = _mod
_spec.loader.exec_module(_mod)
ARGS = _mod.default_base()


def test_cache_equals_fresh_run():
    cached = default_cache.load(*ARGS)
    assert cached is not None, "cache missing or stale: run scripts/build_default_cache.py"
    outs, bands = default_cache.compute(*ARGS)
    assert cached[0] == outs
    assert cached[1] == bands


def test_other_inputs_never_use_cache():
    base, step, ss, sb = ARGS
    assert default_cache.load(replace(base, slots=base.slots + 1), step, ss, sb) is None
    assert default_cache.load(base, step + 1, ss, sb) is None
    assert default_cache.load(base, step, ss + 1, sb) is None


def test_changed_model_forces_recompute(monkeypatch):
    monkeypatch.setattr(default_cache, "fingerprint", lambda: "changed")
    assert default_cache.load(*ARGS) is None
