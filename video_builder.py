import os
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
BLUE_DIR = os.path.join(BASE_DIR, "blue_screens")
CLIPS_DIR = os.path.join(BASE_DIR, "clips")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "10000_cheese.mp4")
CONCAT_FILE = os.path.join(BASE_DIR, "clips_list.txt")

FRAME_SIZE = (128, 128)
HOLD = 3
FADE_DUR = 1


def get_font(size=14):
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
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def create_blue_screen(number, font, path):
    if os.path.exists(path):
        return
    img = Image.new("RGB", FRAME_SIZE, (0, 100, 200))
    draw = ImageDraw.Draw(img)
    text = f"Number: {number}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (128 - tw) // 2
    y = (128 - th) // 2
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx or dy:
                draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    img.save(path)


def make_clip(photo_path, blue_path, clip_path):
    if os.path.exists(clip_path):
        return True

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(HOLD + FADE_DUR), "-i", photo_path,
        "-loop", "1", "-t", str(HOLD + FADE_DUR), "-i", blue_path,
        "-filter_complex",
        f"[0:v]scale=128:128,format=yuv420p,fade=t=in:st=0:d={FADE_DUR}[v0];"
        f"[1:v]scale=128:128,format=yuv420p[v1];"
        f"[v0][v1]xfade=transition=fade:duration={FADE_DUR}:offset={HOLD},"
        f"fade=t=out:st={HOLD + HOLD + FADE_DUR - FADE_DUR}:d={FADE_DUR}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
        "-pix_fmt", "yuv420p",
        clip_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
    return res.returncode == 0


def main():
    os.makedirs(BLUE_DIR, exist_ok=True)
    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    photos = sorted([f for f in os.listdir(VERIFIED_DIR) if f.endswith(".jpg")])[:10000]
    total = len(photos)

    if not photos:
        print(f"No photos found in {VERIFIED_DIR}")
        sys.exit(1)

    print(f"Building video for {total} items (countdown {total} -> 1)...")
    font = get_font(14)

    # 1. Blue transition cards
    for i in range(total):
        num = total - i
        create_blue_screen(num, font, os.path.join(BLUE_DIR, f"{i+1:05d}.png"))

    # 2. Individual clips
    failed = 0
    for i in range(total):
        photo_path = os.path.join(VERIFIED_DIR, photos[i])
        blue_path = os.path.join(BLUE_DIR, f"{i+1:05d}.png")
        clip_path = os.path.join(CLIPS_DIR, f"{i+1:05d}.mp4")

        if not make_clip(photo_path, blue_path, clip_path):
            failed += 1

        if (i + 1) % 100 == 0:
            print(f"[{i+1}/{total}] clips rendered (failed: {failed})")

    # 3. Concatenate all clips
    with open(CONCAT_FILE, "w") as f:
        for i in range(total):
            clip_rel = f"clips/{i+1:05d}.mp4"
            if os.path.exists(os.path.join(BASE_DIR, clip_rel)):
                f.write(f"file '{clip_rel}'\n")

    print("Concatenating clips into final video...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", "clips_list.txt",
        "-c", "copy",
        OUTPUT_FILE
    ]
    res = subprocess.run(cmd, cwd=BASE_DIR)

    if res.returncode == 0:
        mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"Success: {OUTPUT_FILE} ({mb:.1f} MB)")
    else:
        print(f"Concatenation failed with code {res.returncode}")


if __name__ == "__main__":
    main()
