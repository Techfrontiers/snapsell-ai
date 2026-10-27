#!/usr/bin/env python3
"""SnapSell AI demo server (stdlib only, plus PIL for the crop step).

Serves the static gallery from this directory and implements the live
pipeline behind POST /api/process:

    upload photo -> SAM 3.1 box -> padded crop -> Muse Image edits
    (clean studio background) -> Muse Spark Thai listing copy
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
COPY_PROMPT = {
    "th": ("ดูรูปสินค้านี้แล้วเขียนข้อความลงขายแบบ Shopee เป็นภาษาไทย: "
           "ชื่อสินค้า 1 บรรทัด และรายละเอียดสั้นๆ 2-3 ประโยค "
           "ห้ามแต่งราคาหรือคุณสมบัติที่มองไม่เห็นในรูป"),
    "en": ("Look at this product photo and write a Shopee-style listing in English: "
           "a 1-line product title and a short 2-3 sentence description. "
           "Do not invent a price or any spec that is not visible in the photo"),
}
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


def run_pipeline(img_bytes, lang="th"):
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
    status, spark = call("POST", "/chat/completions", {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": COPY_PROMPT.get(lang, COPY_PROMPT["th"])},
            {"type": "image_url", "image_url": {"url": data_url}}]}],
        "max_tokens": 2048}, timeout=180)
    copy_text = ""
    if status == 200:
        copy_text = spark["choices"][0]["message"]["content"] or ""
    return {"ok": True, "concept": concept, "box": box,
            "studio_b64": studio_b64, "copy": copy_text}


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
            try:
                result = run_pipeline(img_bytes, lang)
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
