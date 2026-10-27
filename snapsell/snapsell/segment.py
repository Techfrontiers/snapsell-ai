"""Stage 1 — SAM 3.1 segmentation.

Stub: writes a placeholder mask record with per-photo difficulty flags
taken from the Phase 0 test set. No pixels are segmented in stub mode;
mask_path is null and every consumer must treat the record as a stub.

Live (TODO at switch-on): POST the photo to the SAM 3.1 endpoint from
the official Meta Model API docs, store the returned mask, and fill
mask_path + quality fields. The function signature and output shape do
not change between modes.
"""

import json
import os

from .config import is_live, live_config

# Difficulty flags for the banked test set (observed conditions, not scores).
DIFFICULTY = {
    "1-calbee-bunbun": ["baseline"],
    "2-kopiko-backlit": ["backlit", "hand-in-frame"],
    "3-lactasoy-flash": ["flash-lit"],
    "4-cielo-transparent-busy": ["transparent-bottle", "busy-background"],
    "5-7select-transparent-clean": ["transparent-bottle", "clean-background"],
}


def segment(photo_path: str, out_dir: str) -> dict:
    slug = os.path.splitext(os.path.basename(photo_path))[0]
    record = {
        "stage": "segment",
        "model": "SAM 3.1",
        "photo": os.path.basename(photo_path),
        "difficulty": DIFFICULTY.get(slug, ["unlisted-photo"]),
    }
    if is_live():
        cfg = live_config()
        # TODO(live): POST photo to cfg["base_url"] SAM 3.1 endpoint with
        # cfg["api_key"]; save the mask and set mask_path/quality below.
        # Deliberately unimplemented until credits are confirmed — this
        # path must never be reached in stub mode, and must never run
        # without a key the user set themselves.
        raise NotImplementedError(
            "Live SAM 3.1 call not wired yet: fill in the endpoint from the "
            "official Meta Model API docs, then implement this branch."
        )
    record.update(
        {
            "mode": "stub",
            "mask_path": None,
            "mask_quality": None,
            "note": "STUB — no segmentation performed; placeholder record only.",
        }
    )
    with open(os.path.join(out_dir, "mask.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record
