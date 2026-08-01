# Collections — the Shelf Router

*Rewritten 2026-08-01. Every number here is measured on the real library (user `default`, 83 processed reels, 82 hand-labelled), not estimated.*

---

## 1. What it does

Sorts saved reels onto a small set of **broad** shelves — `Gym & Fitness`, not `Chest Workout` — and leaves everything else off the shelves entirely.

**Coverage is not a goal.** Most reels belong on no shelf; that is the correct outcome, not a failure. They stay reachable through search and Recently saved.

Not to be confused with Smart Folders (`/folders`), which the user creates from a search query and can edit. Collections are system-built and read-only.

---

## 2. The principle

> **Presence is not aboutness.**
> An extractor answers *"what is in this?"*. A shelf answers *"what is this for?"*. The second is never entailed by the first.

Every routing rule keyed on "X appears in the reel" will misfile every reel where X is incidental — a story filmed in a cafe, a car in the background, a place named in passing, clothes on a person who is only dancing. No threshold, embedding or second pass repairs this, because the error is in what the evidence **means**, not in how much of it there is.

Two consequences, both measured:

1. **A describer is one witness, not three.** The vision pass writes the same circumstance into the subject line, the scene sentence *and* the entity lists. Treating that as corroboration is reading one fact three times. Only fields the describer did **not** write — how much anyone actually speaks, and the creator's own caption — can carry purpose.
2. **Withholding a field does not work.** The incidental survives inside the subject sentence, which cannot be dropped because it is the only subject there is. The fix is to **type** the evidence, not hide it.

---

## 3. Pipeline

```
rebuild_library job  ->  worker post-processing (app/workers/process_queue.py)
   -> rebuild_user_shelves(user_id)          app/services/collections.py
        1. one row per REEL (GROUP BY reels.id)
        2. build_card()      -> typed evidence card, or None = not routable
        3. route             -> gpt-4.1-mini x3 seeds, unanimous, cached forever
        4. count + publish   -> collection_shelves / collection_memberships

GET /library  ->  load_shelf_collections()   pure read. No LLM. Ever.
```

Routing happens **only** in the worker. A web request never calls a model and never rebuilds — that is what makes the shelves stable instead of reshuffling between refreshes.

---

## 4. The card

Organised by what each piece of evidence *means*, not by which column it came from:

```
SUBJECT LINE: young woman with long curled hair modeling a beige pullover
SUBJECT KIND: person

WHAT THE REEL DOES (purpose evidence):
- narration: a few words only, nothing explained
- creator's own caption: 🧸 @luciaaferrato

WHAT THE DESCRIBER SAYS IT SHOWS (may state the point, may only state the setting):
- personal style and hair showcasing

WHAT IS PRESENT IN IT (inventory - presence only, never a purpose):
- things visible: beige ribbed pullover; long curled light brown hair; silver hoop earrings
```

Sources: `deep_search_documents.document_json` (main_subject, visual_theme, transcript, caption, visual_entities, brands, product_names, locations) plus `reel_processing_diagnostics.metadata_json -> main_subject_type` and `reel_items` as fallback. Hashtags are stripped — reach tactics, not statements of purpose.

**The unit is the reel, never the reel_item.** Item-level routing let one caption listicle contribute twelve members and manufacture a shelf on its own.

---

## 5. Deciding

**The vocabulary is derived from each user's own library**, not written in code. A batched pass over the reels names the themes that actually recur in *that* collection; those become the shelves, and the model may only select one of them or answer `none`. Someone who saves cricket gets a cricket shelf without anyone editing code.

Breadth is enforced by **support**, not by curation: a theme needs several reels behind it to survive discovery, and a shelf needs `MIN_SHELF_MEMBERS` reels actually routed into it to publish. "Chest Workout" has two and dies; "Gym & Fitness" has twenty and lives.

`FALLBACK_VOCAB` exists only for libraries too small to derive anything from. **Hand-editing it to fix one user's misroute is the mistake this design exists to prevent** — the next user's library is different and there is nobody to file the bug.

Every definition is phrased as a **purpose** — "the reel exists to teach you how to make something" — never as a list of contents, because a contents-phrased definition invites matching against the inventory.

The prompt's rules are tests about evidence, never about a domain: the describer writes presence; repetition is not corroboration; **container test** (shelve the specific thing, never the thing that merely contains it); **swap test** (if a named thing could be swapped and the reel still makes the same point, it is an example, not the subject); when unsure, `none`.

**Gate:** three calls at `temperature=0`, seeds 7/8/9, `gpt-4.1-mini`. All three must return **and** agree. A reel two seeds merely lean on is exactly the reel with no clear purpose. A shelf publishes at ≥ 3 members, capped at 12 shelves.

**Determinism** comes from write-once persistence, not from the model: identical re-runs were measured flipping 1–2 of 83 reels even at temperature 0. Each verdict is stored against `sha256(card)` in `collection_routes` and never recomputed unless the card itself changes.

---

## 6. What was measured

Three arms, three independent seed triples each, ~2,900 real calls:

| Engine | Accuracy vs gold | Precision @ placed | Reels placed |
|---|---|---|---|
| v1 — 2-of-3 votes, contents-phrased vocab | 0.744 | 0.744 | 82 |
| v2 — brand-presence rule | 0.744 | 0.769 | 78 |
| **v3 — presence/aboutness (current)** | **0.805** | **0.844** | 77 |

Paired McNemar, v3 vs v1, pooled over three triples: **b=28, c=9, p=0.0026**. v3 is also the most seed-stable arm (82/83).

**Every graft from the losing designs was measured and rejected** — purpose-first field −5 reels, "silence" clause p=1.0, two-witness reframing p=0.68, sharpened container test −2.

The case that proves the principle — two near-identical reels, both a young woman modelling a garment, separated only by the creator's own words:

```
reel_7    caption "🧸 @luciaaferrato"   -> People & Performance
reel_122  caption "Comment Link 🔗"     -> Fashion & Shopping
```

No entity in either reel distinguishes them. Both have a garment, a person, no brand. The purpose does.

---

## 7. Failure modes it fixes

| Was | Why | Now |
|---|---|---|
| Girl modelling → `Men's Clothing Brands` | clustered `canonical_subdomains` from a keyword heuristic | routes on subject + purpose |
| Girl in a dress → `Fashion` | extractor wrote her outfit down as a "product" | inventory is labelled as presence |
| `Fashion & Style · More 2`, `Failed Reels` | category dump with auto-numbered buckets | fixed vocabulary, failure markers blanked |
| 12 cards from one listicle reel | clustered reel_items | one card per reel |
| Shelves reshuffling every refresh | two engines taking turns; rebuild inside the request | one engine, persisted, read-only requests |

---

## 8. Operations

- `COLLECTIONS_ACCOUNTS` — comma-separated emails or user ids allowed to see shelves. No deploy needed to add one.
- `GET /library/status` — self-diagnosis: allowlist match, signed-in email, routes stored, engine, shelves.
- `POST /library/rebuild` — queue a rebuild.
- Cost: 3 calls per *new or changed* reel, `gpt-4.1-mini`. ~₹6 for a fresh 85-reel library; re-runs are free.
- **Dead key:** cached routes → identical shelves, zero calls. No routes at all → plain category shelves with junk filtered. Never a blank screen.
- Tables `collection_routes` / `collection_shelves` / `collection_memberships` are created by `collections.ensure_schema()` rather than `init_db.py`, because that file held another session's uncommitted work. Idempotent — folding them back later is a no-op.

---

## 9. Known imperfections

- `reel_2` "young man lifting dumbbells in a gym", whose actual subject is regret about quitting the gym, routes to no shelf where the gold label says `Gym & Fitness`. Defensible under a purpose framing; still counted as a miss.
- `A11 Circus underwear` sits in Grooming rather than Fashion; fragrances split across both.
- `Ugly shirt exchange at the airport`, a comedy reel, sits in Fashion.
- `People & Performance` holds 2 reels on this library and so falls below the 3-member floor. It publishes on libraries with more of them — the shelf exists, it just is not padded to fill.
