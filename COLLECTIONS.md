# Collections — how the feature actually works

*Written 2026-08-01 from a full read of the live code plus a real run of the engine against the local 129-item library. Every number below is measured, not estimated.*

---

## 1. What a Collection is

A Collection is an auto-generated shelf of reels. It is **not** the same thing as a Smart Folder:

| | Smart Folders (`/folders`) | Collections (`/library`) |
|---|---|---|
| Created by | the user, from a search query | the system, with no user input |
| Membership decided by | embeddings + `gpt-4.1-mini` adjudication | keyword rules over `reel_item_features` |
| Stored | yes (`folder_memberships`) | **no — recomputed on every page load** |
| Editable | yes (Add / Skip / Rescan) | no |
| Shown on Home | "Your lists" section | "Collections" section |

Collections are stateless. There is no `collections` table. Nothing you see on the Collections shelf is persisted; it is rebuilt from scratch each time the app calls `GET /library`.

---

## 2. The call chain

```
GET /library                                   app/api/routes/library.py:12
  └─ load_library_payload(user_id)             app/services/library.py:802
       ├─ load_personalized_collections()      app/services/library.py:666
       │    ├─ ENGINE A: _build_strong_personalization_collections()   ← wins if it returns anything
       │    └─ ENGINE B: _build_v2_collections()                       ← only if A returned []
       ├─ load_standard_collections()          app/services/library.py:650   ← ENGINE C
       ├─ merge: C fills the gaps A/B left     app/services/library.py:817
       └─ _curate_demo_showcase_collections()  app/services/library.py:766   ← demo account only
```

The UI then renders it:

- `app/ui_ux/clipnest_v1.py:10` injects `SHOW_COLLECTIONS = "1"` **only** when the signed-in user matches `DEMO_ACCOUNT_EMAIL`.
- `clipnest_v1.py:1765` renders the Home "Collections" section behind that flag.
- `clipnest_v1.py:3292` picks `library.personalized` if non-empty, else `library.standard`.
- `clipnest_v1.py:1683` (`isUnsortedList`) hides any shelf whose title is `generic / miscellaneous / uncertain / general / personalized / unsorted`.

So on every account except the demo account, all of this runs on every `/library` call and is then thrown away unrendered.

---

## 3. Engine A — `strong_personalization.py` (this is the one that is live)

1499 lines at repo root. Called with `load_items(db, user_id)` → `build_strong_personalization(items)`.

**Step 1 — seed by rule.** `definition_for_item()` (line 294) is a hand-written if/elif chain. It looks at `canonical_subdomains` from `reel_item_features` and matches them against a fixed whitelist:

```
fragrance · home products · slides and sandals · sneaker culture ·
films and shows · music · app / learning app / job search tools · ai ·
device / audio device / kitchen device / consumer tech / fitness accessories ·
recipes / protein recipes · fitness / wellness · motivation and mindset
+ location-based: restaurants / cafes / street food / dessert spots (→ "Restaurants in {city}")
+ location-based: stay / local rentals (→ "{city} Stay")
+ location-based: destinations / travel planning / cultural experience (→ "{city}")
```

Anything whose subdomain is not on that list returns `None` and becomes **search-only** — invisible in Collections forever.

**Step 2 — quality gate.** `should_publish()` (line 484) drops a candidate shelf unless *all* of these hold:

| Threshold | Value |
|---|---|
| `MIN_ITEMS_TO_PUBLISH` | **5** |
| `MIN_AVG_PAIRWISE_SIMILARITY` | 0.62 |
| `MIN_PAIRWISE_SIMILARITY` | 0.50 (0.42 for located food shelves) |
| `MIN_PURITY` | 0.85 |
| `MIN_MEMBER_SCORE` | 0.72 |
| `RECALL_MEMBER_SCORE` | 0.70 |

**Step 3 — recall pass.** Every item in the library is re-scored against every *surviving* definition; anything ≥ 0.70 joins the best-scoring shelf. The shelf is then re-checked against the full gate, this time with `enforce_min_pairwise=True`.

Shelf titles are **hardcoded strings**, not generated. The complete set of titles this engine can ever produce is: `Fragrances`, `Home Products`, `Slides & Sandals`, `Sneakers`, `Films & Shows`, `Music`, `Apps & Tools`, `Gadgets & Devices`, `Recipes`, `Fitness & Wellness`, `Motivation & Mindset`, `Restaurants in {X}`, `{X} Stay`, `{X}`. Nothing else is possible.

---

## 4. Engine B — `personalization_v2` graph engine (effectively dead)

`app/services/personalization_v2/` — 3600+ lines: graph engine, hybrid router, split/merge, embeddings, normalization.

**It almost never runs.** `load_personalized_collections()` returns Engine A's result the moment it is non-empty. On the local library Engine A publishes one shelf, so Engine B — which would have produced **20** shelves — is skipped entirely.

When it does run (`_build_v2_collections` → `_load_or_build_v2_snapshot`, `library.py:514`) it is also crippled:

- `engine.backfill_user(user_id, use_llm=False, use_remote_embeddings=False)` — **`library.py:537`**.
- `use_remote_embeddings=False` means `embed_text()` falls to `deterministic_embedding()` — a **96-dimension SHA-256 hash bucket** (`embeddings.py:22`). That is not a semantic vector. Cosine similarity over it is noise.
- `backfill_user` starts with `repo.reset_user_state(user_id)` — a full wipe and rebuild of every feature, embedding, node, edge and membership for that user, executed **inline inside the HTTP request**, every time the reel count changes.

---

## 5. Engine C — plain category shelves

`render_mobile_knowledge_app.build_collections_from_rows()` (line 72). No AI at all. It groups `reel_items.primary_category` → `secondary_category` straight from the extraction pipeline, then:

- ≤ 24 items in a primary → one shelf named after the primary category
- a secondary with ≥ 8 items → its own shelf
- > 24 items in a secondary → split into `"{secondary} · Part 1"`, `· Part 2` …
- leftover small secondaries → packed into `"{primary} · More 1"`, `· More 2` …

Engine C is used two ways: as the whole payload when A and B both return nothing, and as **gap-filler** — `library.py:817` appends a C shelf for every reel that A/B did not cover.

---

## 6. The demo-account curation layer

`library.py:751` — `_DEMO_SHOWCASE_KEEP_TITLES`:

```
Restaurants in Bali · Exercise & Training · Nature & Weather ·
Movies · Productivity & Tools · Business & Culture
```

On the demo showcase account **only**, any shelf whose title is not one of those six is silently deleted from the payload (`library.py:769`). A second rule collapses any reel contributing more than 3 items to one shelf down to a single card, to hide caption-listicle blowups (`library.py:780`).

This is why the magic link looks clean: it is a founder-curated allowlist, not a better model. Note the shape of that allowlist — exactly one title (`Restaurants in Bali`) can come from Engine A. The other five are Engine C category shelves. So the demo has effectively **one** AI-built collection and five raw category dumps.

---

## 7. Measured behaviour on the real library (129 items, `default` user)

Ran the live code path end to end. Result:

```
items with features .............. 129
Engine A published shelves ....... 1        (6 items, 4.65% coverage)
Engine A hidden candidates ....... 11
Engine B shelves (never used) .... 20
Engine C shelves ................. 19
final uncurated shelves .......... 20
```

**The one shelf Engine A published:** `Fragrances` — 6 perfumes, purity 1.0.

**The 11 shelves it built and then threw away:**

| Candidate | Items | Purity | Killed by |
|---|---|---|---|
| Gadgets & Devices | 10 | 1.00 | `avg_pairwise 0.6147 < 0.62` |
| Films & Shows | 7 | 0.86 | `avg_pairwise 0.5705 < 0.62` |
| Apps & Tools | 6 | 0.67 | `avg_pairwise` + `purity` |
| Restaurants in Goa | 4 | 1.00 | `item_count < 5` |
| Restaurants in Varanasi | 4 | 1.00 | `item_count < 5` |
| Restaurants in Bali | 2 | 1.00 | `item_count < 5` |
| Music | 1 | 1.00 | `item_count < 5` |
| Recipes | 1 | 1.00 | `item_count < 5` |
| Restaurants in Bangkok | 1 | 1.00 | `item_count < 5` |
| Restaurants in Indonesia | 1 | 1.00 | `item_count < 5` |
| Restaurants in Japan | 1 | 1.00 | `item_count < 5` |

**Where the 123 uncovered items went:**

```
 85  no rule in definition_for_item() matched them at all
 10  gadgets_devices     (shelf failed the gate)
  7  films_shows         (shelf failed the gate)
  6  apps_tools          (shelf failed the gate)
 13  food_places::{goa,varanasi,bali,bangkok,japan,indonesia}
  2  recipes / music
```

Of the 85 that matched no rule, **65 have an empty subdomain list** and **57 have `canonical_domain = "Miscellaneous"`.**

---

## 8. Where the model actually goes wrong — ranked

**1. The "AI" is a keyword heuristic. The LLM never runs.**
Every in-app call site passes `use_llm=False`: `library.py:537` and `routes/personalization_v2.py:22`. The `gpt-4.1-mini` prompt in `interpreter.py:36` is only reachable from the standalone CLI `build_personalization_v2.py`. Confirmed in the DB: **129 / 129 rows have `interpretation_source = 'heuristic'`.** Every collection you have ever seen was built by `heuristic_interpret()` (`interpreter.py:212`), not by a model.

**2. Half the library has no usable features, so it can never be shelved.**
`canonical_subdomains_json = '{}'` (an empty dict, so `as_list()` yields `[]`) for 65 items; `canonical_domain = 'Miscellaneous'` for 57. Real examples from your DB — all tagged Miscellaneous / general / general_reference:
`Legend of Toys Micro Drift Car`, `Hoverpen 2.0 Interstellar Edition`, `retro Macintosh-style dock for Mac Mini M4`, `Lat pulldown grip variations`, `Lateral Breathing for Freestyle Swimming`.
These are obviously Tech and obviously Fitness. The heuristic just has no keyword for them.

**3. `MIN_ITEMS_TO_PUBLISH = 5` deletes your best shelves.**
`Restaurants in Goa` (4 items, purity 1.0, avg pairwise 0.82) and `Restaurants in Varanasi` (4 items, purity 1.0, 0.77) are the highest-quality clusters in the entire library and both are discarded for being one item short. Meanwhile `Fragrances` publishes at 6. The gate is rejecting on *quantity* while the quality signals are perfect.

**4. Location fragmentation splits shelves that should be one.**
`Restaurants in Bali` (2), `Restaurants in Indonesia` (1), `Restaurants in Japan` (1), `Restaurants in Bangkok` (1). Bali and Indonesia are the same trip; Japan and Bangkok are countries/cities used at different granularity. `canonical_location` normalises names but has no place hierarchy, so island / city / country all become sibling shelves — and each one then dies on the 5-item floor. Merged by country these would clear the gate.

**5. `avg_pairwise_similarity < 0.62` kills large, pure shelves by a rounding margin.**
`Gadgets & Devices`: 10 items, purity **1.00**, avg member score 0.958 — dropped because its average pairwise similarity was **0.6147**, i.e. 0.0053 below the line. `pairwise_similarity()` (line 441) gives 27% of its weight to Jaccard overlap of subdomain *strings*, so a charger tagged `["device"]` and earbuds tagged `["audio device","device"]` score only 0.5 on that term. The metric punishes vocabulary variation inside a category that is otherwise perfectly coherent.

**6. Extraction noise leaks straight into clustering.**
`Lattafa Teryaq Intense` (a perfume) carries subdomains `["fragrance", "dessert spots"]`. `dessert spots` is a `FOOD_PLACE_LABEL` — one more of those and the perfume becomes a candidate seed for a restaurants shelf. Nothing validates subdomains against the item.

**7. Engine C's fallback names are user-visible garbage.**
The live uncurated payload contains `Fashion & Style · More 1`, `· More 2`, `· More 3` (auto-numbered buckets from `pack_small_groups`), `Skincare Product Review` (1 item), `Miscellaneous` (1 item), `Personal Growth` (1 item) — and **`Failed Reels` (2 items)**, a processing-failure bucket rendered to the user as if it were a collection.

**8. It recomputes everything on every page load and stores nothing.**
No caching, no persistence, no stable shelf identity. Shelf order is `-item_count, parent, title`, so adding one reel can silently reorder or rename shelves. There is no way for you to correct a mistake, and no record of the mistake to learn from — unlike Smart Folders, which capture Add / Skip / `reject_reason`.

**9. Engine B is 3600 lines of dead weight.**
It produces 20 shelves versus Engine A's 1, and it never gets the chance. If it did run, it would cluster on 96-dim hash vectors.

---

## 9. Fix order, cheapest first

1. **Turn the LLM on.** Flip `use_llm=False` → `True` at `library.py:537`, move the backfill out of the request path into the job queue, and persist. This is the single change that fixes root cause #1 and #2 — but it must not run inline on a GET.
2. **Drop `MIN_ITEMS_TO_PUBLISH` to 3** for shelves with purity ≥ 0.95, or make the floor depend on quality instead of being flat. Recovers Goa and Varanasi immediately.
3. **Add a place hierarchy** (city → region → country) to `canonical_location` and roll up located shelves before the count gate.
4. **Replace subdomain-Jaccard in `pairwise_similarity`** with real embedding cosine, or add label-synonym folding (`audio device` ⊂ `device`). Recovers Gadgets & Devices.
5. **Filter Engine C** — never emit `Failed Reels`, `Miscellaneous`, 1-item shelves, or `· More N` buckets.
6. **Persist collections** with stable ids and add Skip / rename, so mistakes become training signal instead of vanishing on refresh.
7. **Delete Engine B**, or make it the only engine. Having two is why nobody noticed A was covering 4.65% of the library.
