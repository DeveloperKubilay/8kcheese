import os
import sys
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
METADATA_FILE = os.path.join(BASE_DIR, "cat_metadata.json")
# Target 16,000 candidates so that 66% YOLO verification rate yields 10,000+ verified pure cats
TARGET_COUNT = 16000

# Load from environment or local .env
API_KEY = os.getenv("PEXELS_API_KEY", "")
if not API_KEY and os.path.exists(os.path.join(BASE_DIR, ".env")):
    with open(os.path.join(BASE_DIR, ".env")) as f:
        for line in f:
            if line.startswith("PEXELS_API_KEY="):
                API_KEY = line.strip().split("=", 1)[1].strip("\"' ")

# Categorized search terms for 10k cats pipeline
SEARCH_CATEGORIES = {
    "fat_cats": [
        "fat cat", "chubby cat", "chonky cat", "round cat", "fat orange cat",
        "fluffy fat cat", "chubby british shorthair", "fat lazy cat", "big round cat",
        "chonky kitten", "chubby kitten", "chunky cat", "round fat cat", "overweight cat",
        "fat white cat", "fat black cat", "giant cat", "fluffy cat loaf", "fat tabby cat"
    ],
    "breeds": [
        "british shorthair cat", "scottish fold cat", "maine coon cat", "persian cat",
        "ragdoll cat", "siamese cat", "bengal cat", "norwegian forest cat", "sphynx cat",
        "russian blue cat", "munchkin cat", "abyssinian cat", "birman cat", "devon rex cat",
        "chartreux cat", "siberian cat", "turkish van cat", "turkish angora cat",
        "exotic shorthair", "himalayan cat", "oriental shorthair", "ragdoll kitten",
        "maine coon kitten", "persian kitten", "scottish fold kitten", "british shorthair kitten",
        "siamese kitten", "bengal kitten", "burmese cat", "egyptian mau", "somali cat"
    ],
    "colors_patterns": [
        "orange tabby cat", "ginger cat", "calico cat", "tuxedo cat", "black cat",
        "white cat", "tortoiseshell cat", "grey tabby cat", "bicolor cat",
        "fluffy white cat", "fluffy black cat", "ginger tabby", "tabby kitten"
    ],
    "cute_poses": [
        "cat loaf", "sleeping cat", "cute kitten", "fluffy kitten", "cat eyes close up",
        "funny cat", "playful cat", "cat in box", "cat yawning", "cat looking at camera", "cat stretching",
        "cat portrait", "cat whiskers", "feline", "domestic cat", "kitty cat", "cat face"
    ]
}


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

    import argparse
    import shutil
    parser = argparse.ArgumentParser(description="Download cat photos via Pexels API")
    parser.add_argument("--clean", action="store_true", help="Backup and clear existing photos directory for a fresh cat download")
    args = parser.parse_args()

    if args.clean and os.path.exists(PHOTOS_DIR) and os.listdir(PHOTOS_DIR):
        backup_dir = os.path.join(BASE_DIR, "photos_cheese_backup")
        if not os.path.exists(backup_dir):
            print(f"Moving existing photos to {backup_dir}...")
            shutil.move(PHOTOS_DIR, backup_dir)
        else:
            print(f"Backup {backup_dir} already exists.")

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    headers = {"Authorization": API_KEY}

    # Load existing metadata if available
    metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            metadata = {}

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

    executor = ThreadPoolExecutor(max_workers=40)
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

    # Flatten search terms in order: Fat cats first, then breeds, colors, cute poses
    search_queue = []
    for category, terms in SEARCH_CATEGORIES.items():
        is_fat = (category == "fat_cats")
        for term in terms:
            search_queue.append((term, category, is_fat))

    for term, category, is_fat in search_queue:
        if downloaded >= TARGET_COUNT:
            break

        page = 1
        empty_streak = 0
        cat_badge = "[FAT CATS]" if is_fat else f"[{category.upper()}]"
        print(f"\n{cat_badge} Searching: '{term}' (Downloaded: {downloaded}/{TARGET_COUNT})")

        term_photos = 0
        max_per_term = 300 if is_fat else 240
        while empty_streak < 2 and term_photos < max_per_term and (downloaded + len(pending)) < (TARGET_COUNT + 200):
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
                    metadata[str(pid)] = {
                        "term": term,
                        "category": category,
                        "is_fat": is_fat,
                        "width": item.get("width"),
                        "height": item.get("height"),
                        "url": item.get("url")
                    }
                    new_photos += 1
                    term_photos += 1

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

    # Save metadata
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    total_photos = len([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")])
    print(f"Finished. Total photos in {PHOTOS_DIR}: {total_photos}")
    print(f"Metadata saved to {METADATA_FILE}")


if __name__ == "__main__":
    main()
