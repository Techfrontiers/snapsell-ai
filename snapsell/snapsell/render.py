"""Stage 2 — Muse Image studio render.

Stub: copies the input photo (downscaled when Pillow is available) as
studio_mock.jpg and records that it is a PLACEHOLDER COPY, not an AI
render. Any UI or demo that shows this file must label it "MOCK".

Live (TODO at switch-on): send the SAM mask + photo to the Muse Image
endpoint from the official Meta Model API docs and store the returned
studio shot as studio.jpg.
"""

import json
import os
import shutil

from .config import is_live, live_config


def render(photo_path: str, mask_record: dict, out_dir: str) -> dict:
    record = {
        "stage": "render",
        "model": "Muse Image",
        "input_mask_mode": mask_record.get("mode"),
    }
    if is_live():
        cfg = live_config()
        # TODO(live): POST mask + photo to cfg["base_url"] Muse Image
        # endpoint with cfg["api_key"]; save the studio shot as
        # studio.jpg and set studio_path below.
        raise NotImplementedError(
            "Live Muse Image call not wired yet: fill in the endpoint from "
            "the official Meta Model API docs, then implement this branch."
        )
    dest = os.path.join(out_dir, "studio_mock.jpg")
    try:
        from PIL import Image

        im = Image.open(photo_path)
        im.thumbnail((768, 768))
        im.convert("RGB").save(dest, "JPEG", quality=85)
        method = "pillow-downscale-copy"
    except Exception:
        shutil.copyfile(photo_path, dest)
        method = "plain-copy"
    record.update(
        {
            "mode": "stub",
            "studio_path": "studio_mock.jpg",
            "method": method,
            "note": "STUB — studio_mock.jpg is a copy of the input photo, NOT "
            "an AI studio render. Label it MOCK wherever it is shown.",
        }
    )
    with open(os.path.join(out_dir, "studio.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record
