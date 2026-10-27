"""SnapSell AI skeleton CLI.

Usage:
    python3 run.py <photo.jpg> [--cache DIR]
    python3 run.py --all [--cache DIR]

Default mode is stub (no network, no key). Live mode requires
SNAPSELL_MODE=live plus META_MODEL_API_KEY and META_MODEL_API_BASE.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snapsell import pipeline  # noqa: E402
from snapsell.config import mode  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SnapSell AI skeleton pipeline")
    ap.add_argument("photo", nargs="?", help="input photo path")
    ap.add_argument("--all", action="store_true", help="run all test photos")
    ap.add_argument("--cache", default=None, help="cache dir (default: ./cache)")
    args = ap.parse_args()
    cache_root = args.cache or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cache"
    )
    print(f"mode: {mode()}")
    if args.all:
        listings = pipeline.run_all(cache_root)
    elif args.photo:
        listings = [pipeline.run_photo(args.photo, cache_root)]
    else:
        ap.print_help()
        return 2
    for listing in listings:
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        print(f"-> {os.path.join(cache_root, listing['slug'], 'listing.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
