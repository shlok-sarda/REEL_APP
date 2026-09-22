# Final Pipeline Workspace

This folder is the clean working area for the next phase: category-specific prompts and model-guided routing for the 416 saved reels.

## Core 416-Reel Data

- `instagram_saved_reel_urls.txt` - original saved-reel URL list.
- `cache.json` - cached caption/transcript/metadata from reel extraction.
- `reel_store/` - per-reel reusable store from earlier runs.
- `saved_reels_output_v2.csv` - raw model output for all 416 reels.
- `saved_reels_cleaned.csv` - cleaned topic-title output.
- `saved_reels_accumulated.csv` - main final catalog CSV with umbrella/category assignments.
- `saved_reels_topic_graph.json` - graph structure for primary categories, topics, reels, and items.
- `saved_reels_personalized_view.json` - personalized grouping output.

## Current Views / Apps

- `index.html` - static mobile-first knowledge app.
- `saved_reels_standard.html` - standard dashboard.
- `saved_reels_personalized.html` - personalized dashboard.
- `reel_review_app.py` - local review/delete app.

## Model Artifacts

- `reel_classifier.pkl` - trained reel category classifier.
- `tfidf_vectorizer.pkl` - vectorizer used by the classifier.

## Pipeline Scripts

- `finale.py` - reel extraction + visual understanding + classification.
- `data_preprocessing.py` - metadata/transcript/download helpers.
- `run_saved_reels_pipeline.py` - full saved-reels pipeline runner.
- `list_list_name_accumulation.py` - umbrella/category accumulation.
- `merge_existing_topics.py` - semantic topic cleanup.
- `build_topic_graph.py` and `topic_graph.py` - topic graph builder.
- `personalised.py` - personalized grouping.
- `render_catalog.py` and `render_personalized_view.py` - HTML renderers.
- `build_reel_store.py` - local per-reel storage helper.

## Day 2 Backend Foundation

- `api.py` - compatibility launcher that now starts the FastAPI backend.
- `app/main.py` - main FastAPI app.
- `app/api/routes/telegram.py` - Telegram ingest route.
- `app/api/routes/reels.py` - list and delete reel routes.
- `app/api/routes/dashboard.py` - dashboard data route.
- `app/api/routes/health.py` - health check route.
- `app/services/reel_ingest.py` - CSV-backed storage + processing trigger service.
- `app/config.py` - backend settings and paths.
- `app/schemas.py` - request/response models.

### What Day 2 now supports

- env-driven backend settings
- optional `user_id` on ingest
- reel records shaped for future DB migration
- media placeholders:
  - `media_status`
  - `local_video_path`
  - `thumbnail_path`
- CSV storage remains temporary, but the backend contract is now shaped for:
  - database storage
  - downloaded reel playback
  - multi-user separation

## Day 3 Database Foundation

- `app/db/database.py` - low-level SQLite connection helper.
- `app/db/init_db.py` - creates tables and imports legacy Telegram reel inbox data.

### Current Day 3 database tables

- `users`
- `reels`
- `reel_items`
- `product_links`

### What Day 3 changes

- the reel inbox is now database-backed
- existing Telegram reel URLs are imported into SQLite
- CSV remains as a compatibility sync/export for the current processor
- the `reels` table already carries future-facing fields for:
  - `status`
  - `media_status`
  - `local_video_path`
  - `thumbnail_path`

### Initialize the database manually

```bash
cd /Users/shloksarda/Desktop/SBERN/final_pipeline
python3 app/db/init_db.py
```

## Day 4 Downloaded Reel Media

- `app/services/media.py` - downloads persistent reel videos and generates thumbnails.
- `app/main.py` now serves stored media through `/media`.
- `process_shlok_reels.py` now:
  - updates DB reel status
  - downloads stored reel media
  - writes media paths/URLs into the CSV outputs

### Day 4 media folders

- `/Users/shloksarda/Desktop/SBERN/media/Shlok_reels/videos`
- `/Users/shloksarda/Desktop/SBERN/media/Shlok_reels/thumbnails`

### What Day 4 changes

- the app no longer has to rely only on Instagram embed
- stored reel videos and thumbnails are created locally
- generated HTML pages now prefer direct video playback when media exists

## Day 5 Background Jobs

- `app/services/jobs.py` - job queue service backed by SQLite.
- `app/workers/process_queue.py` - background worker that claims and processes reel jobs.
- `app/api/routes/jobs.py` - job inspection route.

### Day 5 job flow

- Telegram ingest creates:
  - a reel record
  - a queued processing job
- a background worker claims jobs one by one
- the worker runs `process_shlok_reels.py` for the specific reel/user
- job states:
  - `pending`
  - `running`
  - `completed`
  - `failed`

### Day 5 reliability improvements

- stale worker lock cleanup
- processor timeout support
- queue/job counts available through backend status

## Day 6 Early Multi-User Separation

- `bot.py` now sends Telegram user id to the backend.
- `process_shlok_reels.py` can now run per user with `--user-id`.
- `app/storage.py` defines per-user library folders.

### Per-user library shape

- default user:
  - `/Users/shloksarda/Desktop/SBERN/Shlok_reels`
- other users:
  - `/Users/shloksarda/Desktop/SBERN/user_libraries/<user_id>_reels`

This is still an early version of multi-user support, but it is enough to keep backend storage and generated dashboards moving toward user separation instead of one global output folder.

## Live Web App (Current Direction)

- `app/services/library.py` - loads user library data for API consumption.
- `app/api/routes/library.py` - serves standard + personalized library JSON.
- `app/api/routes/webapp.py` - serves the mobile-first live web app shell.

### Live routes

- `GET /library?user_id=<telegram_user_id>`
- `GET /app/<telegram_user_id>`
- `GET /` (default user app)

### Current live-app behavior

- mobile-first vertical layout
- collection list view
- item detail view with stored video at the top
- small status center instead of main-screen processing noise
- standard/personalized toggle

### Current backend routes

- `GET /health`
- `POST /telegram-ingest`
- `GET /reels`
- `DELETE /reels/{reel_id}`
- `GET /dashboard`
- `GET /jobs`

### Run the backend

```bash
cd /Users/shloksarda/Desktop/SBERN/final_pipeline
python3 -m pip install fastapi uvicorn
python3 api.py
```

This is still using your existing CSV pipeline under the hood for now, but the API surface is now structured like a deployable backend.

## Per-Reel Processing Cost

Processing one reel costs about **₹0.82** in the current configuration, down from
₹2.68. Measured, not estimated — at ₹88/USD:

| Step | Before | Now | What changed |
|---|---:|---:|---|
| Download (Apify) | 0.24 | 0.24 | unchanged; first ~1,800/month are free |
| Transcription (`gpt-4o-mini-transcribe`) | 0.13 | 0.13 | unchanged |
| Visual pass (`gpt-4.1-mini`, ≤10 keyframes) | 0.69 | **0.11** | `KEYFRAME_MAX_EDGE` |
| Extraction (Pipeline B, 5 calls) | 1.62 | **0.34** | `EXTRACTION_MODEL` |
| **Total** | **2.68** | **0.82** | |

Both levers are environment variables so either can be rolled back from the
Render dashboard without a redeploy. Their defaults in code are the OLD
behaviour, so an unconfigured environment behaves exactly as it did before.

### `EXTRACTION_MODEL` (default `gpt-4.1`, production runs `gpt-4.1-mini`)

Drives Pipeline B's router, both branches, the judge, and the product call.

Measured against the live app's own stored output for **all 439 real user
reels**, with a blind gpt-4.1 judge on every disagreement: titles matched 94%
and were level on quality where they differed (52/48); summaries matched 89%.
Categories are unaffected by this setting — verified by running the genuine
pipeline (real download, real visual pass) on 5 reels, where `gpt-4.1` and
`gpt-4.1-mini` produced identical categories 5/5, and confirmed again on 12
reels reprocessed in production.

### `KEYFRAME_MAX_EDGE` (default `0` = off, production runs `512`)

Downscales each keyframe's long edge before it goes to the visual call.
Keyframes were previously sent at the video's native resolution, roughly 3,300
image tokens for a 1920x1080 frame.

Measured on 30 live reels at native / 768 / 512 / 384, using a **second native
run as the control**: 512px differs from native (`main_subject` similarity
0.811) by less than native differs from itself (0.827), so the resize costs
less than the model's own run-to-run variation. 384px is the first size to fall
clearly below that floor. Set `0` to disable resizing entirely.

`finale.encode_keyframe` falls back to the original bytes when a frame cannot be
read or resized, so a bad frame degrades to the previous behaviour rather than
costing the reel its visuals.

### Costs that are not per-reel

Video storage in R2 is **recurring** and accumulates: ~7.7 MB per reel, about
₹0.30/month for a typical 28-reel user. Processing is paid once; storage is paid
every month, so it becomes a real line item at scale.

## Deployment Notes

### Required environment variables

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `API_HOST=0.0.0.0`
- `API_PORT=8000` locally

### Optional cost-control variables

- `EXTRACTION_MODEL` - see Per-Reel Processing Cost above
- `KEYFRAME_MAX_EDGE` - see Per-Reel Processing Cost above

### Render

- service type: `Web Service`
- root directory: `final_pipeline`
- build command:
  - `pip install -r requirements.txt`
- start command:
  - `API_HOST=0.0.0.0 python3 api.py`

## Debug / Lookup

- `find_reel_location.py` - find where a URL landed in the catalog.
- `debug_single_reel.py` - inspect local debug data for one reel.
- `debug_reel_runner.py` - VS Code-friendly runner for single-reel debugging.
