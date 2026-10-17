"""The shared reel cache survives two workers and a damaged file.

On 2026-10-17 two reels were read at once, both rewrote cache.json, the
writes overlapped and every reel after that failed on import. Plain python:

    python3 tests/test_cache_concurrency.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# The module builds an OpenAI client on import; nothing here calls it.
os.environ.setdefault("OPENAI_API_KEY", "not-used-by-this-test")

import data_preprocessing as dp  # noqa: E402

WRITES_PER_CHILD = 60


def point_cache_at(path: Path) -> None:
    dp.CACHE_FILE = path
    dp.CACHE_LOCK_FILE = path.with_name(path.name + ".lock")
    dp.cache.clear()
    dp.cache.update(dp.read_cache_file())


def child(path: str, prefix: str) -> None:
    point_cache_at(Path(path))
    for index in range(WRITES_PER_CHILD):
        # Big payloads make the overlap that broke prod far more likely.
        dp.save_cache_entry(f"{prefix}{index}", {"caption": prefix * 400, "transcript": str(index) * 300})


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"

        # 1. Whole object followed by junk, exactly like the prod file.
        path.write_text(json.dumps({"keep": {"caption": "x"}}) + 'ion": "tail of the other write"}}')
        point_cache_at(path)
        if dp.cache != {"keep": {"caption": "x"}}:
            failures.append(f"damaged file: expected the whole part kept, got {dp.cache!r}")

        # 2. Nothing readable at all.
        path.write_text("{not json")
        point_cache_at(path)
        if dp.cache != {}:
            failures.append(f"garbage file: expected empty cache, got {dp.cache!r}")

        # 3. Two processes writing at the same time, like WORKER_COUNT=2.
        path.write_text("{}")
        children = [
            subprocess.Popen([sys.executable, __file__, "child", str(path), prefix], cwd=str(ROOT))
            for prefix in ("a", "b")
        ]
        codes = [proc.wait(timeout=120) for proc in children]
        if any(codes):
            failures.append(f"writer processes exited with {codes}")
        try:
            data = json.loads(path.read_text())
        except ValueError as exc:
            failures.append(f"two writers left a broken file: {exc}")
            data = {}
        expected = {f"{prefix}{index}" for prefix in ("a", "b") for index in range(WRITES_PER_CHILD)}
        missing = expected - set(data)
        if missing:
            failures.append(f"two writers lost {len(missing)} of {len(expected)} entries")
        leftovers = [p.name for p in Path(tmp).iterdir() if p.name.endswith(".tmp")]
        if leftovers:
            failures.append(f"temp files left behind: {leftovers}")

    for failure in failures:
        print("FAIL", failure)
    print("ok" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "child":
        child(sys.argv[2], sys.argv[3])
        sys.exit(0)
    sys.exit(main())
