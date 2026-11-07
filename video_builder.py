import os
import sys
import json
import subprocess
import argparse
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
BLUE_DIR = os.path.join(BASE_DIR, "blue_screens")
CLIPS_DIR = os.path.join(BASE_DIR, "clips")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "10000_turkish_foods.mp4")
CONCAT_FILE = os.path.join(BASE_DIR, "clips_list.txt")
VERIFIED_FOOD_FILE = os.path.join(BASE_DIR, "verified_food.json")

FRAME_SIZE = (128, 128)
BLUE_COLOR = (0, 100, 200)
HOLD = 3
FADE_DUR = 1
TOTAL_CLIP_DUR = HOLD + HOLD + FADE_DUR  # 7.0s per item (2s blue card, 2s photo, 1s transitions)


def get_font_path():
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def create_blue_screen(task):
    number, dish_name, font_path, path = task
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return

    try:
        font_main = ImageFont.truetype(font_path, 13) if font_path else ImageFont.load_default()
        font_sub = ImageFont.truetype(font_path, 11) if font_path else ImageFont.load_default()
    except Exception:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    img = Image.new("RGB", FRAME_SIZE, BLUE_COLOR)
    draw = ImageDraw.Draw(img)

    text1 = f"Number: {number}"
    text2 = dish_name[:16] if dish_name and dish_name != "Turkish Food" else ""

    if text2:
        bbox1 = draw.textbbox((0, 0), text1, font=font_main)
        bbox2 = draw.textbbox((0, 0), text2, font=font_sub)
        w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
        w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]

        y1 = (128 - (h1 + h2 + 6)) // 2
        y2 = y1 + h1 + 6
        x1 = (128 - w1) // 2
        x2 = (128 - w2) // 2

        # Shadow
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx or dy:
                    draw.text((x1 + dx, y1 + dy), text1, fill=(0, 0, 0), font=font_main)
                    draw.text((x2 + dx, y2 + dy), text2, fill=(0, 0, 0), font=font_sub)

        draw.text((x1, y1), text1, fill=(255, 255, 255), font=font_main)
        draw.text((x2, y2), text2, fill=(255, 220, 100), font=font_sub)
    else:
        bbox = draw.textbbox((0, 0), text1, font=font_main)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (128 - tw) // 2
        y = (128 - th) // 2
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx or dy:
                    draw.text((x + dx, y + dy), text1, fill=(0, 0, 0), font=font_main)
        draw.text((x, y), text1, fill=(255, 255, 255), font=font_main)

    img.save(path)


def make_clip(task):
    photo_path, blue_path, clip_path, use_gpu = task
    if os.path.exists(clip_path) and os.path.getsize(clip_path) > 1000:
        return True

    # Classic timing:
    # 0s - 1s: Fade in to Number card
    # 1s - 3s: Number card holds for 2s
    # 3s - 4s: 1s crossfade transition into Food photo
    # 4s - 6s: Food photo holds for 2s
    # 6s - 7s: 1s fade out to black
    filter_complex = (
        f"[0:v]scale=128:128,format=yuv420p,fade=t=in:st=0:d={FADE_DUR}[v0];"
        f"[1:v]scale=128:128,format=yuv420p[v1];"
        f"[v0][v1]xfade=transition=fade:duration={FADE_DUR}:offset={HOLD},"
        f"fade=t=out:st={HOLD + HOLD}:d={FADE_DUR}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-threads", "1",
        "-loop", "1", "-t", str(HOLD + FADE_DUR), "-i", blue_path,
        "-loop", "1", "-t", str(HOLD + FADE_DUR), "-i", photo_path,
        "-filter_complex", filter_complex,
        "-t", str(HOLD + HOLD + FADE_DUR),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
        "-threads", "1",
        "-pix_fmt", "yuv420p",
        clip_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
    return res.returncode == 0


def get_sorted_photos(limit=None):
    photos = [f for f in os.listdir(VERIFIED_DIR) if f.endswith(".jpg")]
    dish_names = {}

    if not os.path.exists(VERIFIED_FOOD_FILE):
        photos.sort()
        return [(p, "") for p in (photos[:limit] if limit else photos)]

    try:
        with open(VERIFIED_FOOD_FILE, "r", encoding="utf-8") as f:
            verified_food = json.load(f)

        for p in photos:
            dish_names[p] = verified_food.get(p, {}).get("dish_name", "")

        # Sort so deliciousness score ascends towards #1
        # The #1 spot in the countdown has the highest deliciousness score!
        def sort_key(name):
            data = verified_food.get(name, {})
            return data.get("deliciousness_score", 0.0)

        photos.sort(key=sort_key)
    except Exception as e:
        print(f"Warning: Could not sort by deliciousness_score ({e}), falling back to alphabetical.")
        photos.sort()

    selected = photos[-limit:] if limit else photos
    return [(p, dish_names.get(p, "")) for p in selected]


def check_gpu_support():
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=128x128:rate=1", "-c:v", "h264_amf", "-f", "null", "-"]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="TURBO Multi-Core Turkish Foods Video Generator")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for food countdown (default: all verified foods)")
    parser.add_argument("--workers", type=int, default=None, help="Parallel worker processes (default: all CPU cores)")
    parser.add_argument("--no-gpu", action="store_true", help="Disable AMD AMF GPU encoding and use CPU libx264")
    parser.add_argument("--clean", action="store_true", help="Clean clips and transition cards cache to regenerate all clips")
    args = parser.parse_args()

    if args.clean:
        import shutil
        if os.path.exists(CLIPS_DIR):
            print(f"Clearing old clips cache at {CLIPS_DIR}...")
            shutil.rmtree(CLIPS_DIR)
        if os.path.exists(BLUE_DIR):
            print(f"Clearing old cards cache at {BLUE_DIR}...")
            shutil.rmtree(BLUE_DIR)

    os.makedirs(BLUE_DIR, exist_ok=True)
    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(VERIFIED_DIR):
        print(f"Error: {VERIFIED_DIR} directory does not exist.")
        sys.exit(1)

    photo_tuples = get_sorted_photos(limit=args.limit)
    total = len(photo_tuples)

    if not photo_tuples:
        print(f"No photos found in {VERIFIED_DIR}")
        sys.exit(1)

    output_file = os.path.join(OUTPUT_DIR, f"{total}_turkish_foods.mp4")

    cores = args.workers or multiprocessing.cpu_count()
    use_gpu = not args.no_gpu and check_gpu_support()

    print(f"[CLASSIC TURKISH FOODS VIDEO BUILDER]")
    print(f"   CPU Cores: {cores} parallel processes")
    print(f"   GPU Acceleration: {'AMD AMF Enabled' if use_gpu else 'CPU libx264 ultrafast'}")
    print(f"   Pacing: 7.0s/food (1s fade in, 2s blue card hold, 1s crossfade, 2s food hold, 1s fade out)")
    print(f"   Total items: {total} ALL VERIFIED TURKISH FOODS (Countdown {total} -> 1)")
    print(f"   Target video: {output_file}")

    font_path = get_font_path()

    # 1. Generate blue transition cards in parallel
    print("\n[Stage 1/3] Generating food countdown cards in parallel...")
    card_tasks = [
        (total - i, photo_tuples[i][1], font_path, os.path.join(BLUE_DIR, f"{i+1:05d}.png"))
        for i in range(total)
    ]
    with ProcessPoolExecutor(max_workers=cores) as executor:
        list(executor.map(create_blue_screen, card_tasks))

    # 2. Render micro-clips in parallel using all cores + GPU
    print("\n[Stage 2/3] Rendering video micro-clips in parallel...")
    clip_tasks = [
        (
            os.path.join(VERIFIED_DIR, photo_tuples[i][0]),
            os.path.join(BLUE_DIR, f"{i+1:05d}.png"),
            os.path.join(CLIPS_DIR, f"{i+1:05d}.mp4"),
            use_gpu
        )
        for i in range(total)
    ]

    failed = 0
    with ProcessPoolExecutor(max_workers=cores) as executor:
        futures = {executor.submit(make_clip, task): i for i, task in enumerate(clip_tasks)}
        for count, fut in enumerate(as_completed(futures), 1):
            if not fut.result():
                failed += 1
            if count % 500 == 0 or count == total:
                print(f"[{count}/{total}] clips rendered (failed: {failed})")

    # 3. Concatenate all clips
    print("\n[Stage 3/3] Concatenating clips into final Turkish Foods video...")
    with open(CONCAT_FILE, "w", encoding="utf-8") as f:
        for i in range(total):
            clip_rel = f"clips/{i+1:05d}.mp4"
            if os.path.exists(os.path.join(BASE_DIR, clip_rel)):
                f.write(f"file '{clip_rel}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", "clips_list.txt",
        "-c", "copy",
        output_file
    ]
    res = subprocess.run(cmd, cwd=BASE_DIR)

    if res.returncode == 0:
        mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\nSUCCESS: {output_file} ({mb:.1f} MB)")
        import shutil
        if output_file != OUTPUT_FILE:
            try:
                shutil.copy2(output_file, OUTPUT_FILE)
            except Exception:
                pass
    else:
        print(f"\nFAILED: Concatenation failed with code {res.returncode}")


if __name__ == "__main__":
    main()
