import os
import sys
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
METADATA_FILE = os.path.join(BASE_DIR, "food_metadata.json")
TARGET_COUNT = 14000

# Load from environment or local .env
API_KEY = os.getenv("PEXELS_API_KEY", "")
if not API_KEY and os.path.exists(os.path.join(BASE_DIR, ".env")):
    with open(os.path.join(BASE_DIR, ".env")) as f:
        for line in f:
            if line.startswith("PEXELS_API_KEY="):
                API_KEY = line.strip().split("=", 1)[1].strip("\"' ")

# Categorized search terms for Top 10,000 Turkish Foods
SEARCH_CATEGORIES = {
    "kebabs_and_meats": [
        ("Turkish kebab", "Kebap"),
        ("Adana kebab", "Adana Kebap"),
        ("Urfa kebab", "Urfa Kebap"),
        ("Iskender kebab", "İskender Kebap"),
        ("shish kebab", "Şiş Kebap"),
        ("doner kebab", "Döner"),
        ("shawarma kebab", "Et Döner"),
        ("cig kofte", "Çiğ Köfte"),
        ("Turkish kofte", "Köfte"),
        ("meatballs Turkish", "Izgara Köfte"),
        ("cag kebabi", "Cağ Kebabı"),
        ("beyti kebab", "Beyti"),
        ("sac tava", "Sac Tava"),
        ("kuzu tandir", "Kuzu Tandır"),
        ("kokorec", "Kokoreç"),
        ("ali nazik", "Ali Nazik"),
        ("tas kebabi", "Tas Kebabı"),
        ("etli ekmek", "Etli Ekmek"),
        ("hunkar begendi", "Hünkar Beğendi")
    ],
    "baked_and_street_food": [
        ("lahmacun", "Lahmacun"),
        ("Turkish pide", "Pide"),
        ("borek", "Börek"),
        ("su boregi", "Su Böreği"),
        ("simit", "Simit"),
        ("Turkish bagel", "Susamlı Simit"),
        ("gozleme", "Gözleme"),
        ("pogaca", "Poğaça"),
        ("acma", "Açma"),
        ("tantuni", "Tantuni"),
        ("balik ekmek", "Balık Ekmek"),
        ("midye dolma", "Midye Dolma"),
        ("Turkish flatbread", "Bazlama"),
        ("lavas", "Lavaş"),
        ("kumru sandwich", "Kumru"),
        ("boyoz", "Boyoz"),
        ("karisik tost", "Kaşarlı Tost")
    ],
    "home_stews_and_dishes": [
        ("kuru fasulye", "Kuru Fasulye"),
        ("sarma", "Yaprak Sarma"),
        ("stuffed grape leaves", "Zeytinyağlı Sarma"),
        ("dolma", "Biber Dolması"),
        ("stuffed peppers", "Etli Dolma"),
        ("karniyarik", "Karnıyarık"),
        ("imam bayildi", "İmam Bayıldı"),
        ("manti", "Mantı"),
        ("Turkish dumplings", "Kayseri Mantısı"),
        ("musakka", "Musakka"),
        ("guvec", "Güveç"),
        ("menemen", "Menemen"),
        ("etli guvec", "Etli Güveç"),
        ("lahana sarma", "Lahana Sarması"),
        ("icli kofte", "İçli Köfte")
    ],
    "breakfast_and_meze": [
        ("Turkish breakfast", "Serpme Kahvaltı"),
        ("serpme kahvalti", "Köy Kahvaltısı"),
        ("shakshuka meze", "Şakşuka"),
        ("haydari", "Haydari"),
        ("hummus", "Humus"),
        ("acili ezme", "Acılı Ezme"),
        ("patlican salatasi", "Patlıcan Salatası"),
        ("muhammara", "Muhammara"),
        ("Turkish tea cay", "Türk Çayı"),
        ("Turkish coffee", "Türk Kahvesi"),
        ("kaymak bal", "Bal Kaymak"),
        ("Turkish cheese", "Beyaz Peynir")
    ],
    "desserts_and_sweets": [
        ("baklava", "Baklava"),
        ("Turkish baklava", "Fıstıklı Baklava"),
        ("kunefe", "Künefe"),
        ("kadayif", "Kadayıf"),
        ("sutlac", "Fırın Sütlaç"),
        ("Turkish rice pudding", "Sütlaç"),
        ("kazandibi", "Kazandibi"),
        ("lokum", "Lokum"),
        ("Turkish delight", "Güllü Lokum"),
        ("tulumba", "Tulumba Tatlısı"),
        ("revani", "Revani"),
        ("sekerpare", "Şekerpare"),
        ("Maras dondurma", "Maraş Dondurması"),
        ("helva", "Helva"),
        ("irmik helvasi", "İrmik Helvası"),
        ("trilece", "Trileçe"),
        ("gullac", "Güllaç"),
        ("kemalpasa tatlisi", "Kemalpaşa Tatlısı")
    ],
    "soups": [
        ("mercimek corbasi", "Mercimek Çorbası"),
        ("Turkish lentil soup", "Kırmızı Mercimek Çorbası"),
        ("tarhana corbasi", "Tarhana Çorbası"),
        ("ezogelin soup", "Ezogelin Çorbası"),
        ("yayla corbasi", "Yayla Çorbası"),
        ("iskembe corbasi", "İşkembe Çorbası"),
        ("kelle paca", "Kelle Paça"),
        ("Turkish soup", "Geleneksel Çorba")
    ],
    "general_turkish_cuisine": [
        ("Turkish food", "Türk Mutfağı"),
        ("Turkish cuisine", "Geleneksel Türk Yemeği"),
        ("Turk yemekleri", "Nefis Türk Yemekleri"),
        ("traditional Turkish dish", "Osmanlı Saray Mutfağı"),
        ("Istanbul street food", "Sokak Lezzetleri"),
        ("Turkish restaurant table", "Ziyafet Sofrası")
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
    parser = argparse.ArgumentParser(description="Download Turkish Food photos via Pexels API")
    parser.add_argument("--clean", action="store_true", help="Clear existing photos directory for a fresh download")
    args = parser.parse_args()

    if args.clean and os.path.exists(PHOTOS_DIR) and os.listdir(PHOTOS_DIR):
        print("Cleaning photos directory...")
        shutil.rmtree(PHOTOS_DIR)

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

    # Flatten search terms
    search_queue = []
    for category, items in SEARCH_CATEGORIES.items():
        for query_term, dish_name in items:
            search_queue.append((query_term, dish_name, category))

    for term, dish_name, category in search_queue:
        if downloaded >= TARGET_COUNT:
            break

        page = 1
        empty_streak = 0
        badge = f"[{category.upper()}]"
        print(f"\n{badge} Searching: '{term}' ({dish_name}) - (Downloaded: {downloaded}/{TARGET_COUNT})")

        term_photos = 0
        max_per_term = 200
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
                        "dish_name": dish_name,
                        "category": category,
                        "width": item.get("width"),
                        "height": item.get("height"),
                        "alt": item.get("alt", ""),
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
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    total_photos = len([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")])
    print(f"Finished. Total photos in {PHOTOS_DIR}: {total_photos}")
    print(f"Metadata saved to {METADATA_FILE}")


if __name__ == "__main__":
    main()
