import os
import sys
import json
import shutil
import argparse
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from PIL import Image
import onnxruntime as ort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected")
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.onnx")
METADATA_FILE = os.path.join(BASE_DIR, "cat_metadata.json")
VERIFIED_CATS_FILE = os.path.join(BASE_DIR, "verified_cats.json")

MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.onnx"
CAT_CLASS_INDEX = 15
CAT_CHANNEL_INDEX = 4 + CAT_CLASS_INDEX
TARGET_COUNT = 10000
DEFAULT_CONF_THRESHOLD = 0.35

_worker_session = None


def download_model(dest_path):
    import requests
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"Downloading YOLOv8n ONNX model (~12MB) from {MODEL_URL}...")
    resp = requests.get(MODEL_URL, stream=True, timeout=120)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=16384):
            f.write(chunk)
    print("Model downloaded successfully!")


def init_worker(model_path):
    global _worker_session
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = 1
    _worker_session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])


def is_valid_image(path):
    if not os.path.isfile(path) or os.path.getsize(path) < 500:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def process_image(args):
    filename, src_path, photo_id, conf_thresh, is_fat_query, category, term = args
    if not is_valid_image(src_path):
        return (filename, photo_id, False, 0.0, 0.0, is_fat_query, category, term)

    global _worker_session
    try:
        with Image.open(src_path) as img:
            img_rgb = img.convert("RGB")
            img_resized = img_rgb.resize((640, 640), Image.BILINEAR)

        arr = np.array(img_resized, dtype=np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))
        arr = np.expand_dims(arr, axis=0)

        outputs = _worker_session.run(["output0"], {"images": arr})
        preds = np.transpose(outputs[0][0], (1, 0))

        cat_scores = preds[:, CAT_CHANNEL_INDEX]
        best_idx = int(np.argmax(cat_scores))
        max_score = float(cat_scores[best_idx])

        if max_score < conf_thresh:
            return (filename, photo_id, False, round(max_score, 4), 0.0, is_fat_query, category, term)

        box = preds[best_idx, :4]
        box_w = float(box[2])
        box_h = float(box[3])
        aspect_ratio = min(box_w / (box_h + 1e-6), 2.5)
        area_ratio = min((box_w * box_h) / (640.0 * 640.0), 1.0)

        chonk_score = (aspect_ratio * 1.5) + (area_ratio * 2.5) + (2.0 if is_fat_query else 0.0)
        return (filename, photo_id, True, round(max_score, 4), round(chonk_score, 3), is_fat_query, category, term)
    except Exception:
        return (filename, photo_id, False, 0.0, 0.0, is_fat_query, category, term)


def main():
    parser = argparse.ArgumentParser(description="TURBO Multi-Core AI Cat Verification and Chonkiness Sorter")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF_THRESHOLD, help="Minimum confidence threshold (default: 0.35)")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: all CPU cores)")
    args = parser.parse_args()

    if not os.path.exists(MODEL_PATH):
        download_model(MODEL_PATH)

    os.makedirs(VERIFIED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)

    num_workers = args.workers or multiprocessing.cpu_count()
    print(f"[TURBO MODE] Utilizing {num_workers} CPU cores for parallel AI inference!")

    # Load download metadata
    cat_metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                cat_metadata = json.load(f)
        except Exception:
            pass

    verified_cats = {}
    if os.path.exists(VERIFIED_CATS_FILE):
        try:
            with open(VERIFIED_CATS_FILE, "r", encoding="utf-8") as f:
                verified_cats = json.load(f)
        except Exception:
            pass

    verified_files = set(os.listdir(VERIFIED_DIR))
    rejected_files = set(os.listdir(REJECTED_DIR))
    processed = verified_files | rejected_files

    photos = sorted([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")])
    pending = [f for f in photos if f not in processed]

    print(f"Total candidate photos: {len(photos)}")
    print(f"Already verified: {len(verified_files)} | Rejected: {len(rejected_files)}")
    print(f"Queue for parallel AI processing: {len(pending)}")

    if not pending:
        print("All photos already processed.")
        return

    tasks = []
    for name in pending:
        photo_id = name[:-4]
        meta = cat_metadata.get(photo_id, {})
        tasks.append((
            name,
            os.path.join(PHOTOS_DIR, name),
            photo_id,
            args.conf,
            meta.get("is_fat", False),
            meta.get("category", "unknown"),
            meta.get("term", "")
        ))

    verified_count = len(verified_files)
    rejected_count = len(rejected_files)
    total_tasks = len(tasks)

    print(f"Starting {num_workers}-process pool on {total_tasks} images...")

    with ProcessPoolExecutor(max_workers=num_workers, initializer=init_worker, initargs=(MODEL_PATH,)) as executor:
        futures = {executor.submit(process_image, task): task[0] for task in tasks}

        for i, fut in enumerate(as_completed(futures)):
            filename, photo_id, is_cat, conf, chonk_score, is_fat, category, term = fut.result()
            src = os.path.join(PHOTOS_DIR, filename)

            if is_cat:
                shutil.copy2(src, os.path.join(VERIFIED_DIR, filename))
                verified_count += 1
                verified_cats[filename] = {
                    "id": photo_id,
                    "confidence": conf,
                    "chonk_score": chonk_score,
                    "is_fat": is_fat,
                    "category": category,
                    "term": term
                }
            else:
                shutil.copy2(src, os.path.join(REJECTED_DIR, filename))
                rejected_count += 1

            if (i + 1) % 500 == 0 or (i + 1) == total_tasks:
                print(f"[{i+1}/{total_tasks}] Verified Cats: {verified_count} | Rejected: {rejected_count}")
                with open(VERIFIED_CATS_FILE, "w", encoding="utf-8") as f:
                    json.dump(verified_cats, f, indent=2)

    with open(VERIFIED_CATS_FILE, "w", encoding="utf-8") as f:
        json.dump(verified_cats, f, indent=2)

    print("\n--- Parallel AI Verification Complete ---")
    print(f"Total Verified Cats: {verified_count}")
    print(f"Total Rejected Non-Cats: {rejected_count}")
    print(f"Registry saved: {VERIFIED_CATS_FILE}")


if __name__ == "__main__":
    main()
