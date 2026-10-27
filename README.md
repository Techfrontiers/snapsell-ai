# SnapSell AI 📸

One phone photo in, a ready-to-post listing card out — built for Thai
small sellers who shoot products on their phones: messy background, bad
light, a hand in the frame.

Pipeline: **SAM 3.1** (locate the product) → **Muse Image edits**
(clean studio background, real product and label kept) →
**Muse Spark 1.3** (listing copy from what is actually visible —
never invents a price or a spec that is not in the photo).

- 🎥 **Live demo (gallery):** https://snapsell-demo.pages.dev/
- 🏆 **Event:** Meta Global AI Developer Hackathon 2026, Indie track
  (build window Oct 27 → Nov 5, 2026, submission via Cerebral Valley)

## What works right now

- `demo/` — the demo app. `index.html` is a bilingual (TH/EN) gallery
  of 5 real listing cards plus an upload slot; `server.py` (stdlib +
  PIL) runs the live pipeline behind POST /api/process. Live upload
  needs a Meta Model API key on the machine running the server
  (see `demo/README.md`).
- `snapsell/` — the original pipeline skeleton (stub mode, no API
  spend): segment → render → copywrite, with a per-photo cache layout.
- `docs/` — the build plan and the Devpost pitch draft.

Verified live on 2026-10-27: all 5 test photos (snack bag, backlit
bottle, soy milk carton, transparent bottle on a busy background,
clear water bottle) produce a studio shot with the label preserved
plus accurate Thai copy. Cost ≈ $0.02 per photo at Meta list prices
(SAM $0.0025 + image $0.01 + Spark ≈ $0.007).

## What is NOT built yet (honest gap list)

This is still a demo, not a product. Missing: price suggestion,
batch upload (many photos at once), Shopee/Lazada/TikTok Shop export
or posting, listing history, background/style choices for the studio
shot, and any seller account features. The gallery + upload slot is
the whole app today — that is exactly what needs brainstorming next.

## Run the live demo

```text
cd demo
python3 server.py
```

Then open http://127.0.0.1:8000/ and upload a product photo.
