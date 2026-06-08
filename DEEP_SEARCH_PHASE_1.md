# Deep Search Phase 1

Phase 1 adds a read-only deep-search layer for saved reels.

## Safety

- Does not write to SQLite.
- Does not mutate `reels`, `reel_items`, `product_links`, or `reel_item_features`.
- Indexing writes only to the configured Meilisearch staging index.
- Every API search is scoped by the authenticated `user_id`.

## Routes

Inspect built search documents:

```text
GET /deep-search/documents?user_id=USER_ID&limit=50
```

Search:

```text
GET /deep-search?q=perfume&user_id=USER_ID&limit=20
```

Evaluate a fixed query suite:

```text
GET /deep-search/evaluate?user_id=USER_ID&limit=5
```

Force local fallback:

```text
GET /deep-search?q=perfume&user_id=USER_ID&backend=local
```

Index to staging Meilisearch:

```text
POST /deep-search/index?user_id=USER_ID&index=clipnest_deep_search_reels_staging
```

## Env

```text
MEILI_HOST=
MEILI_MASTER_KEY=
MEILI_INDEX=clipnest_deep_search_reels_staging
```

If `MEILI_HOST` is empty, `/deep-search` uses local weighted search. This is for
testing and does not provide Meilisearch typo/prefix behavior.

If `MEILI_HOST` is configured but the staging index is empty, the first automatic
search seeds the user's documents into Meilisearch and returns local fallback
results immediately. Subsequent searches can use Meilisearch.

## Local Preview

```bash
python3 scripts/deep_search_preview.py --user-id default --query perfume --limit 5
```

Index preview documents into Meilisearch:

```bash
MEILI_HOST=http://127.0.0.1:7700 \
python3 scripts/deep_search_preview.py \
  --user-id user_4a507f088f27007a \
  --index-meili \
  --index clipnest_deep_search_reels_staging
```

## Visual Search

The service reads visual fields from `reel_processing_diagnostics.metadata_json`
when present:

- `relevant_visible_text`
- `visible_text`
- `ocr_text`
- `relevant_visual_entities`
- `visual_entities`
- `objects_items`
- `places`
- `activities`
- `overall_visual_summary`
- `visual_summary`
- `visual_backfill`

If these fields are not present in SQLite, object search still works for
item/product/entity fields, but true visual-only queries need a dedicated search
document export/table that persists extraction-time visual data.
