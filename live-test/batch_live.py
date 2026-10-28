#!/usr/bin/env python3
"""SnapSell Phase 1 batch: remaining 4 photos through SAM + Spark + edits.

For each photo: SAM (concept "product") -> box overlay + padded crop ->
Spark Thai copy -> edits studio shot from the crop. Everything saved
per photo under this directory. Failures are saved as JSON, never hidden.
"""
import base64
import json
import os
import re
import sys

sys.path.insert(0, "/home/hatch/workspace/custom-connectors/custom.meta-model-api/bin")
from meta_api import call
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = "/home/hatch/workspace/goals/meta-global-ai-hackathon-entry/files/snapsell-test-photos"
COPY_PROMPT = ("ดูรูปสินค้านี้แล้วเขียนข้อความลงขายแบบ Shopee เป็นภาษาไทย: "
               "ชื่อสินค้า 1 บรรทัด และรายละเอียดสั้นๆ 2-3 ประโยค "
               "ห้ามแต่งราคาหรือคุณสมบัติที่มองไม่เห็นในรูป")
EDIT_PROMPT = ("Place this exact product on a clean light-grey seamless studio background. "
               "Keep the product, its packaging, colors, label and all text exactly unchanged. "
               "Remove the background completely. Soft even studio lighting, "
               "e-commerce product photo, no extra objects, no added text.")
BOX_RE = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>")


def save(name, obj):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def run_photo(fname):
    slug = fname.rsplit(".", 1)[0]
    path = os.path.join(PHOTOS, fname)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    data_url = "data:image/jpeg;base64," + b64

    status, sam = call("POST", "/responses", {
        "model": "sam-3.1",
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": "product"},
            {"type": "input_image", "image_url": data_url}]}]},
        timeout=300)
    save(slug + "-sam.json", {"status": status, "payload": sam})
    print(slug, "SAM", status)
    box = None
    if status == 200:
        try:
            text = sam["output"][0]["content"][0]["text"]
            m = BOX_RE.search(text)
            if m:
                box = tuple(map(int, m.groups()))
        except (KeyError, IndexError, TypeError):
            box = None
    crop_path = None
    if box:
        x1, y1, x2, y2, w, h = box
        im = Image.open(path).convert("RGB")
        pad = 20
        crop_box = (max(0, x1 - pad), max(0, y1 - pad),
                    min(im.width, x2 + pad), min(im.height, y2 + pad))
        d = ImageDraw.Draw(im)
        d.rectangle([x1, y1, x2, y2], outline=(255, 90, 0), width=8)
        im.save(os.path.join(HERE, slug + "-box.png"))
        crop = Image.open(path).convert("RGB").crop(crop_box)
        crop_path = os.path.join(HERE, slug + "-crop.png")
        crop.save(crop_path)
        print(slug, "BOX", box, "CROP", crop.size)
    else:
        print(slug, "NO BOX FOUND")

    status, spark = call("POST", "/chat/completions", {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": COPY_PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}}]}],
        "max_tokens": 2048}, timeout=180)
    save(slug + "-spark.json", {"status": status, "payload": spark})
    copy_text = ""
    if status == 200:
        copy_text = spark["choices"][0]["message"]["content"] or ""
    print(slug, "SPARK", status, (copy_text[:80] if copy_text else "EMPTY"))

    if crop_path:
        from meta_api import call_multipart
        with open(crop_path, "rb") as f:
            img_bytes = f.read()
        status, payload = call_multipart("/images/edits", {
            "model": "muse-image-1.0", "prompt": EDIT_PROMPT, "n": "1",
            "size": "1024x1024", "response_format": "b64_json",
            "output_format": "png",
        }, [("image", "input.png", img_bytes, "image/png")])
        if status == 200 and isinstance(payload, dict):
            blob = payload.get("data", [{}])[0].get("b64_json")
            if blob:
                with open(os.path.join(HERE, slug + "-studio.png"), "wb") as f:
                    f.write(base64.b64decode(blob))
        print(slug, "EDIT", status)
    else:
        print(slug, "EDIT SKIPPED (no crop)")


if __name__ == "__main__":
    for fname in ["1-calbee-bunbun.jpg", "2-kopiko-backlit.jpg",
                  "3-lactasoy-flash.jpg", "5-7select-transparent-clean.jpg"]:
        run_photo(fname)
    print("BATCH DONE")
