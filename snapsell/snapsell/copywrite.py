"""Stage 3 — Muse Spark Thai listing copy.

Stub: fills Thai listing templates around the photo's filename slug.
The copy is clearly marked as a template (not model output), and the
price suggestion is null on purpose: a real suggestion needs the live
model plus the seller's cost, neither of which the stub invents.

Live (TODO at switch-on): send the studio shot + seller context to the
Muse Spark endpoint from the official Meta Model API docs and parse
title/description/price from the response.

Format variants are structural only in stub mode: each marketplace gets
its own title/description fields so the demo UI can show the variants,
with character counts computed from the actual strings.
"""

import json
import os

from .config import is_live, live_config

MARKETPLACES = ("shopee", "lazada", "tiktok_shop")


def _stub_copy(slug: str) -> dict:
    base_title = f"[STUB] สินค้าจากภาพ {slug}"
    base_desc = (
        f"[STUB] รายละเอียดสินค้าตัวอย่างสำหรับภาพ {slug} — "
        "ข้อความนี้เป็นเทมเพลตของโหมด stub ไม่ใช่ผลลัพธ์จาก Muse Spark "
        "โหมด live จะเขียนชื่อสินค้า คุณสมบัติ และจุดขายจริงจากภาพ"
    )
    formats = {}
    for mp in MARKETPLACES:
        title = base_title
        desc = base_desc
        formats[mp] = {
            "title": title,
            "title_chars": len(title),
            "description": desc,
            "description_chars": len(desc),
        }
    return {
        "stage": "copywrite",
        "model": "Muse Spark",
        "mode": "stub",
        "title_th": base_title,
        "description_th": base_desc,
        "price_suggestion_thb": None,
        "price_note": "STUB — no price suggested; live mode needs the seller's "
        "cost input and the model before suggesting a price.",
        "formats": formats,
        "note": "STUB — template copy only, not Muse Spark output.",
    }


def write_copy(photo_path: str, studio_record: dict, out_dir: str) -> dict:
    slug = os.path.splitext(os.path.basename(photo_path))[0]
    if is_live():
        cfg = live_config()
        # TODO(live): POST studio shot + seller context to cfg["base_url"]
        # Muse Spark endpoint with cfg["api_key"]; parse the response
        # into the same shape _stub_copy returns.
        raise NotImplementedError(
            "Live Muse Spark call not wired yet: fill in the endpoint from "
            "the official Meta Model API docs, then implement this branch."
        )
    record = _stub_copy(slug)
    record["input_studio_mode"] = studio_record.get("mode")
    with open(os.path.join(out_dir, "caption.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record
