# SnapSell AI — skeleton repo (Meta Global AI Hackathon, Indie track)

Phone-photo product-listing studio for Thai small sellers.

Pipeline: **SAM 3.1** cuts out the product → **Muse Image** re-renders a
clean studio shot → **Muse Spark** writes Thai listing copy (title,
description, price suggestion) tuned for Shopee / Lazada / TikTok Shop.

## Modes

**Stub mode is the default.** No network calls, no API key, no cost.
Every stage writes a clearly-labeled placeholder so the pipeline runs
end-to-end on the test photos and the output shape can be reviewed.

**Live mode is gated.** It only runs when `SNAPSELL_MODE=live` AND the
environment variables below are set. Nothing in this repo contains a
credential; config comes from the environment only.

| Variable | Meaning |
|---|---|
| `SNAPSELL_MODE` | `stub` (default) or `live` |
| `META_MODEL_API_KEY` | Meta Model API key (live mode only; never commit) |
| `META_MODEL_API_BASE` | Meta Model API base URL from the official docs (live mode only) |

## Run (stub mode)

```bash
cd snapsell-skeleton
python3 run.py ../snapsell-test-photos/4-cielo-transparent-busy.jpg
# listing JSON: cache/4-cielo-transparent-busy/listing.json
python3 run.py --all   # runs all 5 test photos
```

No third-party dependencies: Python 3.10+ standard library only
(Pillow is used opportunistically for the stub studio copy if installed;
without it the stub falls back to a plain file copy).

## Layout

```
run.py                  CLI entry point
snapsell/
  __init__.py
  config.py             env-based config, mode gate
  segment.py            SAM 3.1 stage (stub mask + live client skeleton)
  render.py             Muse Image stage (stub copy + live client skeleton)
  copywrite.py          Muse Spark stage (stub Thai templates + live client skeleton)
  pipeline.py           runner: photo -> cache/<slug>/{mask,studio,caption,listing}
cache/<slug>/           per-photo outputs (git-ignored, re-runs are free)
  mask.json             segmentation result (stub: placeholder + difficulty flags)
  studio_mock.jpg       stub-mode placeholder (NOT an AI render — labeled in studio.json)
  studio.json           render metadata
  caption.json          copy stage output
  listing.json          final listing: title/description/price/formats
```

## Switching on live mode (only after the $150 credit claim is confirmed)

1. Confirm the credit claim form was submitted and credits are active.
2. Read the official Meta Model API docs for the current endpoint shapes
   and model names (SAM 3.1, Muse Image, Muse Spark) — the live clients
   in `segment.py`, `render.py`, `copywrite.py` mark the exact TODO points.
3. Export the three variables above and run with `SNAPSELL_MODE=live`.
4. Verify on the two hardest test photos first (#4 transparent + busy,
   #2 backlit + hand) before running the full set — those decide whether
   the pipeline is demo-ready.

## Honesty notes (kept in the submission draft too)

- Stub outputs are **placeholders, never presented as AI output**.
- The stub price suggestion is `null`: a real price suggestion needs the
  live model plus the seller's cost input, which the stub does not invent.
- No problem-statement list appears on the public hackathon pages; the
  rubric fit against the portal's problem statements must be verified
  inside the Cerebral Valley portal before submission.
- The published Official Rules never mention certificates; no
  certificate is claimed anywhere in this repo or the draft.
