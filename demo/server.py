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
SELLER_NOTE = {
    "th": "อย่านำเสนอข้อมูลจากผู้ขายว่าเป็นข้อเท็จจริงที่ผ่านการตรวจสอบอิสระแล้ว",
    "en": "Do not present seller claims as independently verified facts.",
}
# Claim categories enforced deterministically (sentence-level strip).
# A category is exempt only when the seller supplied that kind of fact.
# Current-availability wording is NEVER exempt: naming a retailer is
# not proof of current stock (GPT review issue 2).
CATEGORY_PATTERNS = {
    "price": re.compile(r"[฿$]\s*\d|\d+\s*บาท|THB\s*\d|\d+\s*THB", re.I),
    "nutrition": re.compile(r"protein|โปรตีน|vitamin|วิตามิน|nutrition|โภชนาการ|calorie|แคลอรี่|amino|อะมิโน|antioxidant|สารต้านอนุมูลอิสระ|fibre|fiber|ใยอาหาร", re.I),
    "certification": re.compile(r"certif|รับรอง|มาตรฐาน|\bISO\b|\bFDA\b|อย\.|halal|ฮาลาล|organic|ออร์แกนิก|\bGMP\b|\bHACCP\b", re.I),
    "compatibility": re.compile(r"compatible|เข้ากันได้|ใช้กับ|works with|เหมาะสำหรับ|ใช้ได้กับ", re.I),
    "size": re.compile(r"\d+\s*(ml|g|kg|oz|cm|mm|กรัม|กิโลกรัม|มิลลิลิตร|ลิตร|ซม\.?|มม\.?)", re.I),
}
CATEGORY_SELLER_KEYS = {
    "price": ["฿", "$", "บาท", "thb", "price", "ราคา"],
    "nutrition": ["โปรตีน", "protein", "วิตามิน", "vitamin", "โภชนาการ", "nutrition", "แคลอรี่", "calorie", "อะมิโน", "amino"],
    "certification": ["รับรอง", "มาตรฐาน", "certif", "iso", "fda", "อย.", "halal", "ฮาลาล", "organic", "ออร์แกนิก"],
    "compatibility": ["เข้ากันได้", "compatible", "ใช้กับ", "works with", "เหมาะสำหรับ"],
    "size": ["กรัม", "กิโลกรัม", "มิลลิลิตร", "ลิตร", "ml", "ขนาด", "size", "น้ำหนัก", "weight"],
}
RETAILER_TOKENS = ["7-eleven", "เซเว่น"]
GENERIC_AVAIL_PHRASES = ["มีขายที่", "หาซื้อได้ที่", "available at", "sold at"]
AVAIL_KEYWORDS = ["ขาย", "available", "sold", "จำหน่าย", "retail", "store", "ร้าน"]
# --- Value matching (GPT second-pass review) ---
# Price/size claims are kept ONLY when every numeric value in the
# sentence matches a seller-provided value (after unit conversion).
# A same-category keyword is NOT enough: seller "35 baht / 120 g"
# must NOT exempt model "999 baht / 500 g".
def _num(text):
    return round(float(text.replace(",", "")), 2)


def extract_prices(text):
    """All numeric prices in text (currency-marked only)."""
    out = set()
    for m in re.finditer(r"(?:฿|\$|THB)\s*(\d[\d,]*\.?\d*)", text or "", re.I):
        out.add(_num(m.group(1)))
    for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*(?:บาท|baht|THB)", text or "", re.I):
        out.add(_num(m.group(1)))
    return out


_SIZE_UNITS = [
    # (alternatives, dimension, grams/ml/cm per unit) — longer forms first.
    (r"กิโลกรัม|kg", "mass", 1000.0),
    (r"กรัม|\bg\b", "mass", 1.0),
    (r"มิลลิลิตร|ml", "volume", 1.0),
    (r"ลิตร", "volume", 1000.0),
    (r"ซม\.?|cm", "length", 1.0),
    (r"มม\.?|mm", "length", 0.1),
]


def extract_sizes(text):
    """All (dimension, canonical value) size pairs in text."""
    out = set()
    for alts, dim, factor in _SIZE_UNITS:
        for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*(?:" + alts + r")",
                             text or "", re.I):
            out.add((dim, round(_num(m.group(1)) * factor, 2)))
    return out


# Health-benefit claims are NEVER seller-exempt: a seller asserting a
# cure does not verify it. Narrow list on purpose (see LIMITATIONS).
HEALTH_BENEFIT_RE = re.compile(
    r"cure|cures|treats|heals|รักษาโรค|บรรเทาอาการ|ป้องกันโรค|"
    r"เสริมภูมิคุ้มกัน|detox|ล้างพิษ", re.I)

# LIMITATIONS (stated plainly, GPT second-pass review item 3):
# - Regex catches listed keywords/patterns only. Paraphrases,
#   misspellings, Thai phrasing variants, implied claims
#   ("feel fresh all day"), and claims split across sentences
#   are NOT caught.
# - Value matching covers NUMERIC prices and MEASURED sizes only.
#   Non-numeric price mentions, vague sizes ("big bag"), flavor,
#   variant, and subjective puffery are NOT value-checked.
# - Nutrition/certification/compatibility exemptions are still
#   keyword-based (not value-verified) — only price and size
#   got value matching in this round.
# - A seller-value match proves CONSISTENCY with seller input
#   only, never independent truth. Matched values stay labelled
#   as seller-provided, never as verified.

CURRENT_AVAIL_RE = re.compile(r"ทั่วประเทศ|nationwide|ทุกสาขา|all branches|in stock|พร้อมส่ง", re.I)
PRICE_RE = CATEGORY_PATTERNS["price"]


def parse_copy(copy_text, lang="th"):
    """Split Spark output into (description, needs, diagnostic).

    FAIL-CLOSED (GPT review issue 1): if the NEEDS_CONFIRMATION
    marker is missing, the raw text is NOT trusted as listing copy.
    Description falls back to the minimal safe line; the raw output
    is returned only as a diagnostic (never rendered as listing
    copy by the UI). Empty model output behaves the same way.
    """
    lang = lang if lang in FALLBACK_NEEDS else "th"
    lines = (copy_text or "").splitlines()
    marker_idx = None
    for i, line in enumerate(lines):
        if line.strip().rstrip(":") == "NEEDS_CONFIRMATION":
            marker_idx = i
            break
    if marker_idx is None:
        diagnostic = (copy_text or "").strip() or "empty model output"
        return MIN_DESC[lang], [FALLBACK_NEEDS[lang]], diagnostic
    desc = "\n".join(lines[:marker_idx]).strip()
    needs = [ln.strip()[1:].strip() for ln in lines[marker_idx + 1:]
             if ln.strip().startswith("-") and ln.strip()[1:].strip()]
    if not desc:
        desc = MIN_DESC[lang]
        if not needs:
            needs = [FALLBACK_NEEDS[lang]]
    return desc, needs, None


def _split_units(text):
    """Split a description into sentence-ish units (title line + sentences)."""
    units = []
    for block in (text or "").split("\n"):
        block = block.strip()
        if not block:
            continue
        units.extend(u.strip() for u in re.split(r"(?<=[.!?])\s+", block) if u.strip())
    return units


def enforce_claims(description, seller_facts, lang="th"):
    """Fail-closed claim enforcement (replaces flag-only check_claims).

    Returns (safe_description, removed_needs). A sentence unit that
    makes a claim in an enforced category WITHOUT a matching seller
    fact is REMOVED from the description and quoted in removed_needs
    as a diagnostic (labelled removed, not listing copy). Seller
    facts exempt their category, EXCEPT current-availability wording,
    which is never exempt: naming a retailer is not proof of current
    stock. Subjective puffery (tasty, easy to carry) is not a factual
    category and is left to the prompt + needs section — documented
    limitation, not a claim of full enforcement.
    """
    lang = lang if lang in FALLBACK_NEEDS else "th"
    seller = (seller_facts or "").lower()
    prefix = "ตัดออกเพื่อยืนยัน" if lang == "th" else "Removed for verification"
    seller_prices = extract_prices(seller_facts)
    seller_sizes = extract_sizes(seller_facts)
    kept, removed = [], []
    for unit in _split_units(description):
        low = unit.lower()
        hit = None
        if HEALTH_BENEFIT_RE.search(unit):
            hit = "health-benefit"
        else:
            prices = extract_prices(unit)
            if prices:
                if not seller_prices:
                    hit = "price-unverified"
                elif not prices.issubset(seller_prices):
                    hit = "price-mismatch"
            if hit is None:
                sizes = extract_sizes(unit)
                if sizes:
                    if not seller_sizes:
                        hit = "size-unverified"
                    elif not sizes.issubset(seller_sizes):
                        hit = "size-mismatch"
        if hit is None:
            for cat, rx in CATEGORY_PATTERNS.items():
                if cat in ("price", "size"):
                    continue
                if rx.search(unit) and not any(k in seller for k in CATEGORY_SELLER_KEYS[cat]):
                    hit = cat
                    break
        if hit is None:
            if RETAILER_TOKENS and any(t in low for t in RETAILER_TOKENS) \
                    and not any(t in seller for t in RETAILER_TOKENS):
                hit = "availability"
            elif any(ph in low for ph in GENERIC_AVAIL_PHRASES) \
                    and not any(k in seller for k in AVAIL_KEYWORDS):
                hit = "availability"
        if hit is None and CURRENT_AVAIL_RE.search(unit):
            hit = "current-availability"
        if hit is not None:
            removed.append(f"{prefix} ({hit}): {unit}")
        else:
            kept.append(unit)
    safe = "\n".join(kept) if kept else MIN_DESC[lang]
    return safe, removed


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
        prompt_text += ("\n\nSeller-provided claims (NOT independently verified; "
                        "a seller mention is not proof of current availability or stock):\n"
                        + seller_facts.strip())
    else:
        prompt_text += "\n\nSeller-provided facts: none."
    prompt_text += "\n" + SELLER_NOTE.get(lang, SELLER_NOTE["th"])
    status, spark = call("POST", "/chat/completions", {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}}]}],
        "max_tokens": 2048}, timeout=180)
    copy_text = ""
    if status == 200:
        copy_text = spark["choices"][0]["message"]["content"] or ""
    description_raw, needs, diagnostic = parse_copy(copy_text, lang)
    safe_desc, removed = enforce_claims(description_raw, seller_facts, lang)
    for entry in removed:
        if entry not in needs:
            needs.append(entry)
    return {"ok": True, "concept": concept, "box": box,
            "studio_b64": studio_b64, "copy": safe_desc,
            "description": safe_desc, "needs_confirmation": needs,
            "diagnostic_untrusted": diagnostic,
            "seller_facts_used": bool((seller_facts or "").strip())}


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
