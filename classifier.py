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
MODELS_DIR = os.path.join(BASE_DIR, "models", "swin_food")
MODEL_PATH = os.path.join(MODELS_DIR, "model_quantized.onnx")
CONFIG_PATH = os.path.join(MODELS_DIR, "config.json")
METADATA_FILE = os.path.join(BASE_DIR, "food_metadata.json")
VERIFIED_FOOD_FILE = os.path.join(BASE_DIR, "verified_food.json")

MODEL_URL = "https://huggingface.co/onnx-community/swin-finetuned-food101-ONNX/resolve/main/onnx/model_quantized.onnx"
CONFIG_URL = "https://huggingface.co/onnx-community/swin-finetuned-food101-ONNX/raw/main/config.json"

DEFAULT_CONF_THRESHOLD = 0.14
DEFAULT_LOGIT_THRESHOLD = 3.6
DEFAULT_TOP3_THRESHOLD = 0.32

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_worker_session = None
_worker_id2label = None


def download_model():
    import urllib.request
    os.makedirs(MODELS_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading Swin Food ONNX model (~89MB) from {MODEL_URL}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model downloaded successfully!")
    if not os.path.exists(CONFIG_PATH):
        print("Downloading food class config...")
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)
        print("Config downloaded successfully!")


def init_worker(model_path, config_path):
    global _worker_session, _worker_id2label
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = 1
    _worker_session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
    with open(config_path, "r", encoding="utf-8") as f:
        _worker_id2label = json.load(f).get("id2label", {})


def is_valid_image(path):
    if not os.path.isfile(path) or os.path.getsize(path) < 1000:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def compute_visual_richness(img):
    try:
        arr = np.array(img, dtype=np.float32) / 255.0
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        v = maxc
        deltac = maxc - minc
        s = np.where(maxc == 0, 0, deltac / (maxc + 1e-6))

        warmth = float(np.mean((r > b) & (r > 0.25)))
        saturation = float(np.mean(s))
        contrast = float(np.std(v))
        return saturation, contrast, warmth
    except Exception:
        return 0.3, 0.2, 0.3


def process_image(args):
    filename, src_path, photo_id, conf_thresh, logit_thresh, top3_thresh, dish_name, category, term = args
    if not is_valid_image(src_path):
        return (filename, photo_id, False, 0.0, 0.0, "corrupt", dish_name, category, term)

    global _worker_session, _worker_id2label
    try:
        with Image.open(src_path) as img:
            img_rgb = img.convert("RGB")
            sat, contrast, warmth = compute_visual_richness(img_rgb)
            img_resized = img_rgb.resize((224, 224), Image.Resampling.BICUBIC)

        arr = ((np.array(img_resized, dtype=np.float32) / 255.0) - MEAN) / STD
        arr = np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)

        logits = _worker_session.run(None, {"pixel_values": arr})[0][0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)

        top1_idx = int(np.argmax(probs))
        top1_prob = float(probs[top1_idx])
        top1_logit = float(logits[top1_idx])
        top3_prob = float(np.sum(np.sort(probs)[-3:]))
        predicted_food = _worker_id2label.get(str(top1_idx), f"class_{top1_idx}")

        # Verification gate:
        # Accepts food photos, dining tables, waiters/people serving or eating food
        # Strictly rejects cars, buildings, empty landscapes, unrelated portraits
        is_food = (top1_logit >= logit_thresh) and (top1_prob >= conf_thresh or top3_prob >= top3_thresh)

        # Deliciousness score for ranking appetizing Turkish dishes first
        # Combines AI food certainty with rich warm tones, saturation, and contrast
        deliciousness_score = (
            (top1_prob * 3.5) +
            (min(top1_logit, 12.0) * 0.3) +
            (sat * 2.5) +
            (warmth * 2.0) +
            (contrast * 1.5)
        )

        return (
            filename,
            photo_id,
            is_food,
            round(top1_prob, 4),
            round(deliciousness_score, 3),
            predicted_food,
            dish_name,
            category,
            term
        )
    except Exception as e:
        return (filename, photo_id, False, 0.0, 0.0, f"error_{e}", dish_name, category, term)


def main():
    parser = argparse.ArgumentParser(description="Multi-Core AI Turkish Food Verification and Deliciousness Sorter")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF_THRESHOLD, help="Minimum top-1 confidence (default: 0.14)")
    parser.add_argument("--logit", type=float, default=DEFAULT_LOGIT_THRESHOLD, help="Minimum logit threshold (default: 3.6)")
    parser.add_argument("--top3", type=float, default=DEFAULT_TOP3_THRESHOLD, help="Minimum top-3 confidence (default: 0.32)")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: all CPU cores)")
    args = parser.parse_args()

    if not os.path.exists(MODEL_PATH) or not os.path.exists(CONFIG_PATH):
        download_model()

    os.makedirs(VERIFIED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)

    num_workers = args.workers or multiprocessing.cpu_count()
    print(f"[TURBO MODE] Utilizing {num_workers} CPU cores for parallel AI food classification!")

    food_metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                food_metadata = json.load(f)
        except Exception:
            pass

    verified_food = {}
    if os.path.exists(VERIFIED_FOOD_FILE):
        try:
            with open(VERIFIED_FOOD_FILE, "r", encoding="utf-8") as f:
                verified_food = json.load(f)
        except Exception:
            pass

    verified_files = set(os.listdir(VERIFIED_DIR))
    rejected_files = set(os.listdir(REJECTED_DIR))
    processed = verified_files | rejected_files

    photos = sorted([f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")]) if os.path.exists(PHOTOS_DIR) else []
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
        meta = food_metadata.get(photo_id, {})
        tasks.append((
            name,
            os.path.join(PHOTOS_DIR, name),
            photo_id,
            args.conf,
            args.logit,
            args.top3,
            meta.get("dish_name", "Turkish Food"),
            meta.get("category", "cuisine"),
            meta.get("term", "")
        ))

    verified_count = len(verified_files)
    rejected_count = len(rejected_files)
    total_tasks = len(tasks)

    print(f"Starting {num_workers}-process pool on {total_tasks} images...")

    with ProcessPoolExecutor(max_workers=num_workers, initializer=init_worker, initargs=(MODEL_PATH, CONFIG_PATH)) as executor:
        futures = {executor.submit(process_image, task): task[0] for task in tasks}

        for i, fut in enumerate(as_completed(futures)):
            filename, photo_id, is_food, conf, deliciousness, pred_food, dish_name, category, term = fut.result()
            src = os.path.join(PHOTOS_DIR, filename)

            if is_food:
                shutil.copy2(src, os.path.join(VERIFIED_DIR, filename))
                verified_count += 1
                verified_food[filename] = {
                    "id": photo_id,
                    "confidence": conf,
                    "deliciousness_score": deliciousness,
                    "predicted_food": pred_food,
                    "dish_name": dish_name,
                    "category": category,
                    "term": term
                }
            else:
                shutil.copy2(src, os.path.join(REJECTED_DIR, filename))
                rejected_count += 1

            if (i + 1) % 500 == 0 or (i + 1) == total_tasks:
                print(f"[{i+1}/{total_tasks}] Verified Foods: {verified_count} | Rejected: {rejected_count}")
                with open(VERIFIED_FOOD_FILE, "w", encoding="utf-8") as f:
                    json.dump(verified_food, f, indent=2, ensure_ascii=False)

    with open(VERIFIED_FOOD_FILE, "w", encoding="utf-8") as f:
        json.dump(verified_food, f, indent=2, ensure_ascii=False)

    print("\n--- Parallel AI Food Verification Complete ---")
    print(f"Total Verified Foods: {verified_count}")
    print(f"Total Rejected Non-Food: {rejected_count}")
    print(f"Registry saved: {VERIFIED_FOOD_FILE}")


if __name__ == "__main__":
    main()
