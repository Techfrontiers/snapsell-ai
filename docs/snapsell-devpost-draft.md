# SnapSell AI — Devpost draft (Phase 0, NOT submitted)

Status: **DRAFT ONLY — do not submit.** Phase 0 skeleton built 2026-10-27.
Live Meta Model API not yet tested (credit claim confirmation pending).
Nothing here has been posted to the Cerebral Valley portal or Devpost.

Event: Meta Global AI Hackathon, Indie Developer track (solo).
Window: Tue Oct 27 00:00 → Thu Nov 5 09:00 Bangkok.
Submission: via the Cerebral Valley portal (one track only).

## Pitch (English, submission-ready draft)

**SnapSell AI — snap a messy phone photo, get a studio-quality listing in 60 seconds.**

Thailand's small online sellers lose sales to ugly product photos. Hiring a
photographer costs more than their margin, and existing AI tools assume clean
studio shots and write in English. SnapSell AI is built for the photos sellers
actually take: cluttered background, bad lighting, a hand in the frame.

One photo goes through three Meta models in one pipeline:

1. **SAM 3.1** cuts the product out — including the hard cases: transparent
   bottles, reflections, backlight, occlusion by a hand.
2. **Muse Image** re-renders the cutout as a clean studio product shot.
3. **Muse Spark** writes the Thai title, description, and price suggestion,
   formatted for Shopee, Lazada, and TikTok Shop.

## How it maps to the OFFICIAL rubric

Official weights (Hackathon Terms & Conditions, "Official Rules", 2026-10-25):

- **Impact — 30%.** The user is a Thai small seller who shoots on a phone
  in a shop, market stall, or living room. The win is concrete: a listing
  that looks professional without a photographer, a studio, or English
  copywriting skills. The rubric also weighs whether the project fits one
  of the event's problem statements — **that fit must still be verified
  inside the Cerebral Valley portal** (no problem-statement list appears
  on the public event pages, so none is claimed here).
- **Use of Meta AI Tooling — 25%.** Three Meta models chained, not one
  API call: segmentation → image generation → Thai copy. The chain only
  works if the first step survives transparency and backlight — that is
  the engineering bet, and the demo leads with those two cases.
- **Demo — 25%.** A live before/after: the seller's original messy photo
  next to the studio shot and the ready-to-post Thai listing, in the
  marketplace's own format. The demo uses the five banked test photos,
  including the two hardest (transparent bottle on a busy background;
  backlit shot with a hand in frame).
- **Technical Depth & Execution — 20%.** A real pipeline, not a mock:
  cached stages (mask → studio → caption → listing JSON) so re-runs cost
  nothing, per-photo difficulty flags, and format variants per
  marketplace. The Phase 0 skeleton runs end-to-end in stub mode today;
  the live clients are written behind an env flag and switch on once
  credits are confirmed.

## Demo plan (for the video)

1. Seller takes a messy phone photo (busy background / backlight).
2. SAM 3.1 cutout shown (mask overlay) — the hard case, not the easy one.
3. Muse Image studio shot appears next to the original.
4. Thai title + description + price suggestion render in Shopee format,
   then switch to Lazada and TikTok Shop variants.
5. Copy-paste into the marketplace (manual step — the tool does not
   auto-post to any marketplace).

## 10-day schedule (brief)

- **Days 1–2 (Oct 27–28):** Phase 0 — skeleton, stub pipeline, mock UI,
  this draft. Confirm credit claim; verify problem-statement fit in portal.
- **Days 3–4:** Live API switch-on; run all 5 test photos; score the two
  hardest cases; fix the pipeline where segmentation fails.
- **Days 5–7:** Listing flow polish (photo → studio → Thai copy),
  marketplace format variants, price suggestion with seller cost input.
- **Days 8–9:** Demo video (before/after on the hardest photos) +
  submission writeup.
- **Day 10 (Nov 5):** Final check, submit via portal before 09:00 Bangkok.

## Honesty notes (do not strip these before submitting)

- No achievements are claimed beyond what exists: the pipeline is a
  Phase 0 skeleton in stub mode; live-model results do not exist yet.
- No problem statement is claimed: fit must be verified in the portal.
- No certificate is claimed: the published Official Rules never mention
  certificates.
- The author's prior work (JudgePay, PayPal AI Hackathon entry, 162/162
  tests; a pre-launch WooCommerce dropship store) is real and may be
  mentioned as background, but it is not part of this project's results.
- All submission materials (photos, copy, video) will be the project's
  own work; test photos are the author's own product shots.
