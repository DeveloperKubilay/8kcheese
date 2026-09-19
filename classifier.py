import os
import shutil
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected")
TARGET_COUNT = 10000


def is_valid_image(path):
    if not os.path.isfile(path) or os.path.getsize(path) < 500:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def main():
    os.makedirs(VERIFIED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)

    verified = set(os.listdir(VERIFIED_DIR))
    rejected = set(os.listdir(REJECTED_DIR))
    processed = verified | rejected

    photos = sorted([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")])
    pending = [f for f in photos if f not in processed]

    print(f"Total: {len(photos)} | Verified: {len(verified)} | Pending: {len(pending)}")

    verified_count = len(verified)
    rejected_count = len(rejected)

    for i, name in enumerate(pending):
        if verified_count >= TARGET_COUNT:
            print(f"Target count ({TARGET_COUNT}) reached.")
            break

        src = os.path.join(PHOTOS_DIR, name)
        if is_valid_image(src):
            shutil.copy2(src, os.path.join(VERIFIED_DIR, name))
            verified_count += 1
        else:
            shutil.copy2(src, os.path.join(REJECTED_DIR, name))
            rejected_count += 1

        if (i + 1) % 500 == 0:
            print(f"[{i+1}/{len(pending)}] Verified: {verified_count} | Rejected: {rejected_count}")

    print(f"Done. Verified: {verified_count}, Rejected: {rejected_count}")


if __name__ == "__main__":
    main()
