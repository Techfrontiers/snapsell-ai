# SnapSell AI — demo app

Phone photo in, listing card out. Pipeline: SAM 3.1 (find the product)
-> Muse Image edits (clean studio background, product and label kept)
-> Muse Spark 1.3 (Thai listing copy from what is actually visible).

## Files

- `index.html` — the app. Works opened statically: the 5 gallery cards
  are real pipeline outputs. The upload slot needs the server below.
- `server.py` — stdlib server (plus PIL for the crop). Serves the page
  and runs the live pipeline at POST /api/process. Localhost only.
- `assets/` — before/after images for the 5 gallery cards.
- `deploy_pages.py` — deploys this directory to Cloudflare Pages
  project `snapsell-demo` (public gallery, upload slot inactive there).

## Run the live demo

```text
python3 server.py
```

Then open http://127.0.0.1:8000/ and upload a product photo.
Live mode calls Meta Model API through the `meta_api.py` helper, which
authenticates via the connected meta-model-api account on the machine
running the server. Without that connection only the static gallery works.

## Notes from testing (2026-10-27)

- SAM's concept phrase must be a concrete noun. The server retries
  product -> bottle -> package -> box until a box comes back, because
  a generic concept can return completed-but-empty output.
- Spark 1.3 is always-thinking: max_tokens must be >= 2048 or the
  reply comes back empty.
- Price is deliberately left as "— (รอระบบแนะนำราคา)": the copy step
  never invents a price or a spec that is not visible in the photo.
