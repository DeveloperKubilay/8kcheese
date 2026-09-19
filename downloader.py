import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
TARGET_COUNT = 10000

# Load from environment or local .env
API_KEY = os.getenv("PEXELS_API_KEY", "")
if not API_KEY and os.path.exists(os.path.join(BASE_DIR, ".env")):
    with open(os.path.join(BASE_DIR, ".env")) as f:
        for line in f:
            if line.startswith("PEXELS_API_KEY="):
                API_KEY = line.strip().split("=", 1)[1].strip("\"' ")

SEARCH_TERMS = [
    "cheese", "cheddar", "brie", "gouda", "mozzarella",
    "parmesan", "feta", "camembert", "swiss cheese", "cream cheese",
    "gruyere", "roquefort", "cottage cheese", "ricotta", "provolone",
    "pecorino", "blue cheese", "halloumi", "mascarpone", "emmental",
    "cheese platter", "cheese board", "cheese slice", "melted cheese",
    "cheese wheel", "cheese block", "mac and cheese", "grilled cheese",
    "cheese fondue", "cheese pizza",
]


def download_image(photo_id, url):
    dest = os.path.join(PHOTOS_DIR, f"{photo_id}.jpg")
    if os.path.exists(dest):
        return True

    for attempt in range(3):
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                with open(dest, "wb") as f:
                    f.write(res.content)
                return True
        except requests.RequestException:
            if attempt < 2:
                time.sleep(0.5)
    return False


def fetch_page(query, page, headers):
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": 80, "page": page}

    for attempt in range(4):
        try:
            res = requests.get(url, headers=headers, params=params, timeout=20)
            if res.status_code == 429:
                delay = min(2 ** attempt * 2, 30)
                print(f"[!] Rate limited. Waiting {delay}s...")
                time.sleep(delay)
                continue
            res.raise_for_status()
            return res.json()
        except requests.RequestException as err:
            if attempt == 3:
                print(f"[!] Request failed for '{query}' (page {page}): {err}")
            time.sleep(1.5)
    return None


def main():
    if not API_KEY:
        print("Error: PEXELS_API_KEY is not set. Please set it as an environment variable or in .env")
        sys.exit(1)

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    headers = {"Authorization": API_KEY}

    existing = {
        int(f[:-4])
        for f in os.listdir(PHOTOS_DIR)
        if f.endswith(".jpg") and f[:-4].isdigit()
    }
    downloaded = len(existing)
    seen_ids = set(existing)

    print(f"Target: {TARGET_COUNT} | Existing: {downloaded}")
    if downloaded >= TARGET_COUNT:
        print("Target already reached.")
        return

    executor = ThreadPoolExecutor(max_workers=10)
    pending = {}

    def flush_done(wait=False):
        nonlocal downloaded
        done_keys = []
        for pid, fut in pending.items():
            if fut.done() or wait:
                try:
                    if fut.result(timeout=30 if wait else 0):
                        downloaded += 1
                except Exception:
                    pass
                done_keys.append(pid)
        for pid in done_keys:
            del pending[pid]

    for term in SEARCH_TERMS:
        if downloaded >= TARGET_COUNT:
            break

        page = 1
        empty_streak = 0
        print(f"\nSearching: '{term}' (Downloaded: {downloaded}/{TARGET_COUNT})")

        while empty_streak < 2 and (downloaded + len(pending)) < (TARGET_COUNT + 200):
            data = fetch_page(term, page, headers)
            if not data or not data.get("photos"):
                empty_streak += 1
                page += 1
                continue

            new_photos = 0
            for item in data["photos"]:
                pid = item["id"]
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    pending[pid] = executor.submit(download_image, pid, item["src"]["tiny"])
                    new_photos += 1

            empty_streak = 0 if new_photos > 0 else empty_streak + 1
            flush_done(wait=False)
            page += 1
            time.sleep(0.1)

            if not data.get("next_page"):
                break

        flush_done(wait=False)

    print("\nWaiting for remaining downloads...")
    flush_done(wait=True)
    executor.shutdown(wait=True)

    total_photos = len([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")])
    print(f"Finished. Total photos in {PHOTOS_DIR}: {total_photos}")


if __name__ == "__main__":
    main()
