#!/usr/bin/env python3
"""Deploy snapsell-demo dir to Cloudflare Pages project 'helios'
via the official Pages Direct Upload API flow:
  1. GET upload-token (API token auth, via the same surrogate helper cf.py uses)
  2. POST /pages/assets/upload (JWT auth) — file blobs keyed by md5(content)
  3. POST /pages/assets/upsert-hashes (JWT auth)
  4. POST deployments with multipart form field 'manifest' (API token auth)
  5. Poll the deployment until it succeeds or fails.
Never prints any token/JWT value — only ids, urls and statuses.
Usage: deploy_pages.py [dist_dir]
"""
import base64, hashlib, json, mimetypes, os, sys, time, urllib.request, uuid

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

ACCOUNT = "8548e0cf2304a5cd14ecb69199f02d31"
PROJECT = "snapsell-demo"
BASE = "https://api.cloudflare.com/client/v4"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def call(method, path, body=None, content_type=None, bearer=None):
    req = urllib.request.Request(BASE + path, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    if bearer is not None:
        req.add_header("Authorization", "Bearer " + bearer)
    else:
        add_surrogate_to_request(req, "custom.cloudflare", allowed_hosts=["api.cloudflare.com"])
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as resp:
        return read_json_response(resp)


def main():
    dist = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "dist")
    files = []
    for root, _dirs, names in os.walk(dist):
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = "/" + os.path.relpath(full, dist).replace(os.sep, "/")
            data = open(full, "rb").read()
            files.append((rel, data, mimetypes.guess_type(full)[0] or "application/octet-stream"))
    print(f"files: {len(files)}, total bytes: {sum(len(d) for _, d, _ in files)}")
    manifest = {}
    uploads = []
    for rel, data, ctype in files:
        h = hashlib.md5(data).hexdigest()
        manifest[rel] = h
        uploads.append({"key": h, "value": base64.b64encode(data).decode(), "metadata": {"contentType": ctype}, "base64": True})
    tok = call("GET", f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/upload-token")
    jwt = tok["result"]["jwt"] if isinstance(tok["result"], dict) else tok["result"]
    print("upload token: obtained (value not printed)")
    up = call("POST", "/pages/assets/upload", json.dumps(uploads).encode(), "application/json", bearer=jwt)
    print("asset upload success:", up.get("success"))
    hashes = sorted({m for m in manifest.values()})
    uh = call("POST", "/pages/assets/upsert-hashes", json.dumps({"hashes": hashes}).encode(), "application/json", bearer=jwt)
    print("upsert-hashes success:", uh.get("success"))
    boundary = "----helios" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="manifest"\r\n'
        "Content-Type: application/json\r\n\r\n"
        + json.dumps(manifest)
        + f"\r\n--{boundary}--\r\n"
    ).encode()
    dep = call("POST", f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments",
               body, f"multipart/form-data; boundary={boundary}")
    d = dep["result"]
    dep_id, url, env = d["id"], d.get("url"), d.get("environment")
    print(f"deployment created: id={dep_id} url={url} environment={env}")
    for _ in range(60):
        time.sleep(10)
        cur = call("GET", f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments/{dep_id}")
        stage = cur["result"]["latest_stage"]
        print(f"poll: stage={stage['name']} status={stage['status']}")
        if stage["status"] == "success":
            print(f"DEPLOY SUCCESS id={dep_id} url={url}")
            return 0
        if stage["status"] in ("failure", "error"):
            print(f"DEPLOY FAILED id={dep_id} stage={stage}")
            return 1
    print("DEPLOY TIMEOUT (still polling-able)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
