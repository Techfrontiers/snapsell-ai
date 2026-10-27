"""Pipeline runner: photo -> cache/<slug>/{mask,studio,caption,listing}.

Cache layout means re-runs are free: outputs are overwritten in place
and nothing is re-fetched (stub mode makes no network calls at all).
"""

import json
import os

from . import copywrite, render, segment
from .config import mode

TEST_PHOTOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "snapsell-test-photos",
)


def run_photo(photo_path: str, cache_root: str) -> dict:
    slug = os.path.splitext(os.path.basename(photo_path))[0]
    out_dir = os.path.join(cache_root, slug)
    os.makedirs(out_dir, exist_ok=True)
    mask = segment.segment(photo_path, out_dir)
    studio = render.render(photo_path, mask, out_dir)
    caption = copywrite.write_copy(photo_path, studio, out_dir)
    listing = {
        "slug": slug,
        "photo": os.path.basename(photo_path),
        "pipeline_mode": mode(),
        "title_th": caption["title_th"],
        "description_th": caption["description_th"],
        "price_suggestion_thb": caption["price_suggestion_thb"],
        "price_note": caption["price_note"],
        "formats": caption["formats"],
        "stages": {
            "segment": mask.get("mode"),
            "render": studio.get("mode"),
            "copywrite": caption.get("mode"),
        },
        "difficulty": mask.get("difficulty"),
    }
    with open(os.path.join(out_dir, "listing.json"), "w", encoding="utf-8") as f:
        json.dump(listing, f, ensure_ascii=False, indent=2)
    return listing


def run_all(cache_root: str) -> list:
    photos = sorted(
        p
        for p in (
            os.path.join(TEST_PHOTOS_DIR, f)
            for f in sorted(os.listdir(TEST_PHOTOS_DIR))
        )
        if p.lower().endswith(".jpg")
    )
    return [run_photo(p, cache_root) for p in photos]
