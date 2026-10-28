# Live-test evidence (Oct 27, 2026)

Batch runner + API response evidence for the 5-photo pipeline test.

- `batch_live.py` — batch runner: SAM 3.1 box → crop → Muse Image
  studio shot → Muse Spark Thai copy, via the Meta Model API helper
  (no credential in this repo; the helper authenticates through the
  connected account on the machine that runs it).
- `*-sam.json`, `*-spark.json` — saved API responses for photos
  1, 2, 3, 5 (Calbee, Kopiko, Lactasoy, 7-Select).
- Photo 4 (Cielo, transparent + busy background) has no batch JSON
  here; its result is visible in `demo/assets/before4.jpg` /
  `after4.jpg` and in the public demo gallery (it was run through
  the demo server path, not this batch script).

Deliberately NOT included: intermediate box/crop/studio PNGs
(regenerable by running `batch_live.py`), probe intermediates,
`__pycache__`, deployment configs, and any credential — none of
those belong in this repo. Studio results for all 5 photos are in
`demo/assets/` (before/after JPGs) and at the demo gallery.
