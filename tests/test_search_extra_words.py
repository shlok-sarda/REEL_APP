"""Checks that a search still finds a reel when the person adds a word the
reel never mentions (a city, a typo, a stray "i"). Plain python, no pytest:

    python3 tests/test_search_extra_words.py

Measured miss this guards: "work from cafe i banglore" found nothing while
"work from cafe" found the reel. Embeddings are faked and kept weak on
purpose, so only the word matching decides, the same as that miss.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OPENAI_API_KEY", "sk-disabled-local-test")

from app.services import deep_search_hybrid as hybrid  # noqa: E402

MUMBAI_CAFE = {
    "id": "1", "reel_id": "mumbai_cafe",
    "main_subject": "Laptop-friendly cafe for working",
    "item_names": ["Work from cafe spots"], "locations": ["Mumbai"],
    "visual_summary": "A person works on a laptop in a cozy cafe",
    "primary_category": "Food & Drink",
}
BANGALORE_CAFE = {
    "id": "4", "reel_id": "bangalore_cafe",
    "main_subject": "Quiet cafe to work from",
    "item_names": ["Work from cafe in Indiranagar"], "locations": ["Bengaluru", "Indiranagar"],
    "visual_summary": "People on laptops at a cafe",
    "primary_category": "Food & Drink",
}
OTHERS = [
    {"id": "2", "reel_id": "butter_chicken", "main_subject": "Butter chicken",
     "item_names": ["Butter chicken"], "locations": ["Delhi"], "primary_category": "Food"},
    {"id": "3", "reel_id": "gym", "main_subject": "Gym workout",
     "item_names": ["Push ups"], "primary_category": "Fitness"},
]

# Weak, flat semantic scores: the semantic lanes admit nothing, so the
# result rests on the word lanes alone.
hybrid.embed_remote = lambda text: [1.0, 0.0, 0.0, 0.0]
hybrid._load_vector = lambda rid, kind: [0.1, 0.99, 0.0, 0.0]


def found(documents, query):
    return [r["reel_id"] for r in hybrid.search_documents_hybrid(documents, query)]


failures = 0


def check(name, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got}, want {want}")


library = [MUMBAI_CAFE] + OTHERS
check("plain words still work", found(library, "work from cafe"), ["mumbai_cafe"])
check("extra city word, misspelled", found(library, "work from cafe i banglore"), ["mumbai_cafe"])
check("city the reel is not in", found(library, "cafes in indiranagar"), ["mumbai_cafe"])
check("nonsense still finds nothing", found(library, "blorptastic frimble"), [])
check("one unknown word finds nothing", found(library, "cats"), [])

library = [MUMBAI_CAFE, BANGALORE_CAFE] + OTHERS
check("banglore matches a Bengaluru reel only", found(library, "work from cafe i banglore"), ["bangalore_cafe"])
check("bangalore matches a Bengaluru reel only", found(library, "work from cafe in bangalore"), ["bangalore_cafe"])
check("indiranagar picks the right cafe", found(library, "cafes in indiranagar"), ["bangalore_cafe"])
check("mumbai picks the right cafe", found(library, "work from cafe in mumbai"), ["mumbai_cafe"])
check("bombay means mumbai", found(library, "cafe in bombay"), ["mumbai_cafe"])

fts = [r["reel_id"] for r in hybrid.search_documents_fts([MUMBAI_CAFE] + OTHERS, "work from cafe i banglore")]
check("backup search (no OpenAI) too", fts, ["mumbai_cafe"])

print("ALL PASS" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
