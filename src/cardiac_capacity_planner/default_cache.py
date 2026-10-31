"""Precomputed result for the default inputs, so the first screen appears at once.

The cache file is written by ``scripts/build_default_cache.py``. It is only used when the inputs
equal the defaults AND the model fingerprint (a hash of the simulation and scenario code) still
matches. Otherwise the live simulation runs, as before. A stale cache can never be used silently.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from cardiac_capacity_planner import scenarios

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / "cache" / "default_run.json"
SRC = Path(__file__).resolve().parents[1]


def fingerprint() -> str:
    """Hash of the code that makes the numbers (line endings ignored)."""
    h = hashlib.sha256()
    files = sorted((SRC / "cardiac_capacity").glob("*.py")) + [SRC / "cardiac_capacity_planner" / "scenarios.py"]
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def key(base, step: int, ss: int, sb: int) -> str:
    """Hash of the inputs (the full policy, so any default change changes the key)."""
    return hashlib.sha256(repr((base, step, ss, sb)).encode()).hexdigest()


def compute(base, step: int, ss: int, sb: int):
    """The live run: the single code path used by the app and by the cache builder."""
    opts = scenarios.options(base.slots, base.beds, step)
    outs = [scenarios.evaluate(base, o, ss, sb) for o in opts]
    bands = {o.key: scenarios.weekly_list(base, o) for o in opts}
    return outs, bands


def _pack(outs, bands) -> dict:
    return {"outs": [asdict(o) for o in outs], "bands": {k: [list(x) for x in v] for k, v in bands.items()}}


def _unpack(d: dict):
    outs = []
    for o in d["outs"]:
        o = dict(o)
        o["option"] = scenarios.Option(**o["option"])
        o["by_diagnosis"] = tuple(tuple(x) for x in o["by_diagnosis"])
        outs.append(scenarios.Outcome(**o))
    bands = {k: tuple(list(x) for x in v) for k, v in d["bands"].items()}
    return outs, bands


def write(base, step: int, ss: int, sb: int) -> Path:
    outs, bands = compute(base, step, ss, sb)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": fingerprint(), "key": key(base, step, ss, sb), **_pack(outs, bands)}
    CACHE_FILE.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return CACHE_FILE


def load(base, step: int, ss: int, sb: int):
    """The cached result, or None if missing, stale or for other inputs."""
    try:
        d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if d["fingerprint"] != fingerprint() or d["key"] != key(base, step, ss, sb):
            return None
        return _unpack(d)
    except (OSError, ValueError, KeyError, TypeError):
        return None
