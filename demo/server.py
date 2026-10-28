#!/usr/bin/env python3
"""SnapSell AI demo server (stdlib only, plus PIL for the crop step).

Serves the static gallery from this directory and implements the live
pipeline behind POST /api/process:

    upload photo -> SAM 3.1 box -> padded crop -> Muse Image edits
    (clean studio background) -> Muse Spark evidence-first listing copy (EN/TH) with a separate Needs confirmation section (Phase 1)
    -> JSON with the studio image and the copy.

Run:  python3 server.py [port]        (default 8000, localhost only)
Open: http://127.0.0.1:8000/

Live mode calls Meta Model API through the meta_api.py helper, which
authenticates via the connected meta-model-api account on this machine.
Without that connection only the static gallery works.
"""
import base64
import io
import json
import os
import re
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.expanduser(
    "~/workspace/custom-connectors/custom.meta-model-api/bin"))
from meta_api import call, call_multipart  # noqa: E402

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BOX_RE = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>")
# SAM needs a concrete noun. A generic concept can come back empty, so
# retry with more specific nouns before giving up.
CONCEPTS = ["product", "bottle", "package", "box"]
# Phase 1 (evidence-first guardrail): copy only from visible evidence +
# seller-provided facts. Anything unsupported goes in a delimited
# NEEDS_CONFIRMATION section, never in the title/description. The
# marker is identical in both languages so the parser stays simple.
COPY_PROMPT = {
    "th": ("เขียนข้อความลงขายจากหลักฐานเท่านั้น: ใช้เฉพาะสิ่งที่มองเห็น"
           "ในรูปสินค้า และข้อมูลที่ผู้ขายให้มาเท่านั้น "
           "ห้ามแต่งราคา คุณสมบัติทางโภชนาการ การรับรอง ความเข้ากันได้ "
           "หรือความพร้อมจำหน่าย ถ้าข้อมูลใดไม่มีหลักฐาน ห้ามใส่ในชื่อ"
           "หรือรายละเอียด ให้ใส่ในส่วน NEEDS_CONFIRMATION แทน "
           "เขียนชื่อสินค้า 1 บรรทัด และรายละเอียด 2-3 ประโยคจาก"
           "ข้อเท็จจริงที่ยืนยันได้เท่านั้น อย่าปล่อยให้รายละเอียดว่างเปล่า"
           "ถ้ายังมีข้อเท็จจริงที่ยืนยันได้ รูปแบบผลลัพธ์:\n"
           "[ชื่อสินค้า]\n[รายละเอียด]\nNEEDS_CONFIRMATION:\n"
           "- [ข้อมูลที่ต้องยืนยันทีละข้อ]"),
    "en": ("Write a listing ONLY from evidence: use only what is visible "
           "in the product photo and facts supplied by the seller. "
           "Do not invent a price, nutritional properties, certification, "
           "compatibility, or availability. If a fact has no evidence, "
           "do NOT put it in the title or description; put it in the "
           "NEEDS_CONFIRMATION section instead. Write a 1-line title and "
           "a 2-3 sentence description from confirmed facts only; do not "
           "leave the description empty while confirmed facts exist. "
           "Output format:\n[title]\n[description]\nNEEDS_CONFIRMATION:\n"
           "- [one item to confirm per line]"),
}
FALLBACK_NEEDS = {
    "th": "แยกข้อเท็จจริงที่ยืนยันได้กับที่ยังยืนยันไม่ได้ไม่ออก — ตรวจสอบก่อนลงขาย",
    "en": "Could not separate confirmed facts from unconfirmed claims — verify before listing",
}
NEEDS_PRICE = {
    "th": "ราคาปรากฏในข้อความแต่ผู้ขายไม่ได้ให้ราคามา — ยืนยันราคาก่อนลงขาย",
    "en": "Price appears in the copy but no price was supplied — verify price before listing",
}
NEEDS_AVAIL = {
    "th": "ข้อความอ้างความพร้อมจำหน่ายหรือร้านที่ขายแต่ผู้ขายไม่ได้ให้ข้อมูลนี้มา — ยืนยันก่อนลงขาย",
    "en": "Availability or a retailer is mentioned but not supplied — verify before listing",
}
MIN_DESC = {
    "th": "สินค้าตามในรูป.",
    "en": "Product shown in the photo.",
}
PRICE_RE = re.compile(r"[฿$]\s*\d|\d+\s*บาท|THB\s*\d|\d+\s*THB", re.I)
# Retailer tokens are checked precisely (a seller fact phrased as
# "sold at 7-Eleven" must satisfy a copy claim phrased as
# "available at 7-Eleven"). Generic availability phrases fall back to
# checking whether the seller supplied ANY availability wording at all.
RETAILER_TOKENS = ["7-eleven", "เซเว่น"]
GENERIC_AVAIL_PHRASES = ["มีขายที่", "หาซื้อได้ที่", "available at", "sold at"]
AVAIL_KEYWORDS = ["ขาย", "available", "sold", "จำหน่าย", "retail", "store", "ร้าน"]


def parse_copy(copy_text, lang="th"):
    """Split Spark output into (description, needs_confirmation).

    Pure function (no network) so it is unit-testable. If the model
    omits the NEEDS_CONFIRMATION marker, the whole text is kept as the
    description and a fallback warning is added — never silently
    shipped as verified, never crashed.
    """
    lang = lang if lang in FALLBACK_NEEDS else "th"
    lines = (copy_text or "").splitlines()
    marker_idx = None
    for i, line in enumerate(lines):
        if line.strip().rstrip(":") == "NEEDS_CONFIRMATION":
            marker_idx = i
            break
    if marker_idx is None:
        desc = (copy_text or "").strip()
        needs = [FALLBACK_NEEDS[lang]]
    else:
        desc = "\n".join(lines[:marker_idx]).strip()
        needs = [ln.strip()[1:].strip() for ln in lines[marker_idx + 1:]
                 if ln.strip().startswith("-") and ln.strip()[1:].strip()]
    if not desc:
        desc = MIN_DESC[lang]
        if not needs:
            needs = [FALLBACK_NEEDS[lang]]
    return desc, needs


def check_claims(description, seller_facts, lang="th"):
    """Deterministic post-checks on the description (pure, testable).

    Flags, never silently deletes: a flagged claim stays visible in
    the description but is also listed under needs_confirmation, so
    the seller verifies before publishing.
    """
    lang = lang if lang in FALLBACK_NEEDS else "th"
    seller = (seller_facts or "").lower()
    needs = []
    price_supplied = any(t in seller for t in ["฿", "$", "บาท", "thb", "price", "ราคา"])
    if PRICE_RE.search(description or "") and not price_supplied:
        needs.append(NEEDS_PRICE[lang])
    desc_lower = (description or "").lower()
    avail_flagged = False
    for retailer in RETAILER_TOKENS:
        if retailer in desc_lower and retailer not in seller:
            avail_flagged = True
            break
    if not avail_flagged:
        for phrase in GENERIC_AVAIL_PHRASES:
            if phrase in desc_lower and not any(k in seller for k in AVAIL_KEYWORDS):
                avail_flagged = True
                break
    if avail_flagged:
        needs.append(NEEDS_AVAIL[lang])
    return needs
EDIT_PROMPT = ("Place this exact product on a clean light-grey seamless studio background. "
               "Keep the product, its packaging, colors, label and all text exactly unchanged. "
               "Remove the background completely. Soft even studio lighting, "
               "e-commerce product photo, no extra objects, no added text.")


def sam_box(data_url):
    """Try concepts in order until SAM returns a box. Returns (box, concept)."""
    for concept in CONCEPTS:
        status, sam = call("POST", "/responses", {
            "model": "sam-3.1",
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": concept},
                {"type": "input_image", "image_url": data_url}]}]},
            timeout=300)
        if status != 200:
            continue
        try:
            text = sam["output"][0]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            continue
        m = BOX_RE.search(text or "")
        if m:
            return tuple(map(int, m.groups())), concept
    return None, None


def run_pipeline(img_bytes, lang="th", seller_facts=""):
    data_url = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode()
    box, concept = sam_box(data_url)
    if not box:
        return {"ok": False, "error": "SAM หาสินค้าในรูปไม่เจอ ลองถ่ายให้เห็นสินค้าชัดกว่านี้"}
    x1, y1, x2, y2, w, h = box
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pad = 20
    crop = im.crop((max(0, x1 - pad), max(0, y1 - pad),
                    min(im.width, x2 + pad), min(im.height, y2 + pad)))
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    status, payload = call_multipart("/images/edits", {
        "model": "muse-image-1.0", "prompt": EDIT_PROMPT, "n": "1",
        "size": "1024x1024", "response_format": "b64_json",
        "output_format": "png",
    }, [("image", "input.png", buf.getvalue(), "image/png")])
    if status != 200 or not isinstance(payload, dict):
        return {"ok": False, "error": "วาดรูปสตูดิโอไม่สำเร็จ"}
    studio_b64 = payload.get("data", [{}])[0].get("b64_json")
    if not studio_b64:
        return {"ok": False, "error": "วาดรูปสตูดิโอไม่สำเร็จ"}
    prompt_text = COPY_PROMPT.get(lang, COPY_PROMPT["th"])
    if (seller_facts or "").strip():
        prompt_text += ("\n\nSeller-provided facts (seller input, not image evidence):\n"
                        + seller_facts.strip())
    else:
        prompt_text += "\n\nSeller-provided facts: none."
    status, spark = call("POST", "/chat/completions", {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}}]}],
        "max_tokens": 2048}, timeout=180)
    copy_text = ""
    if status == 200:
        copy_text = spark["choices"][0]["message"]["content"] or ""
    description, needs = parse_copy(copy_text, lang)
    for extra in check_claims(description, seller_facts, lang):
        if extra not in needs:
            needs.append(extra)
    return {"ok": True, "concept": concept, "box": box,
            "studio_b64": studio_b64, "copy": description,
            "description": description, "needs_confirmation": needs}


# Abuse guard for the public tunnel: the server spends the owner's Meta
# credits per upload, so cap uploads per client IP per hour.
RATE_LIMIT_PER_IP_PER_HOUR = 20
_rate = {}


def rate_ok(ip):
    now = time.time()
    hits = [t for t in _rate.get(ip, []) if now - t < 3600]
    if len(hits) >= RATE_LIMIT_PER_IP_PER_HOUR:
        return False
    hits.append(now)
    _rate[ip] = hits
    return True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def log_message(self, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/api/process":
            self.send_error(404)
            return
        import cgi
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={"REQUEST_METHOD": "POST",
                                         "CONTENT_TYPE": self.headers.get("Content-Type", "")})
        if not rate_ok(self.client_address[0]):
            result = {"ok": False,
                      "error": "ถึงลิมิตการอัปโหลดแล้ว (20 ครั้ง/ชั่วโมง) / Upload limit reached (20/hour)"}
        elif "photo" not in form or not form["photo"].file:
            result = {"ok": False, "error": "ไม่พบไฟล์รูป"}
        else:
            img_bytes = form["photo"].file.read()
            lang = form.getvalue("lang", "th") if "lang" in form else "th"
            facts = form.getvalue("facts", "") if "facts" in form else ""
            try:
                result = run_pipeline(img_bytes, lang, facts)
            except Exception as e:  # never leak a stack trace to the client
                result = {"ok": False, "error": "pipeline ล้ม: %s" % e}
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("SnapSell demo at http://127.0.0.1:%d/  (Ctrl-C to stop)" % port)
    server.serve_forever()
