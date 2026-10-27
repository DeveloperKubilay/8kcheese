import os
import sys
import json
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
FRAMES_DIR = os.path.join(BASE_DIR, "frames")
VERIFIED_CATS_FILE = os.path.join(BASE_DIR, "verified_cats.json")

FRAME_SIZE = (128, 128)
CARD_COLOR = (15, 65, 140)
TEXT_COLOR = (255, 255, 255)
MAX_PHOTOS = 10000

FPS = 15
HOLD_FRAMES = FPS * 3
FADE_FRAMES = FPS * 1


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


def create_photo_frame(photo_path):
    with Image.open(photo_path) as img:
        return img.convert("RGB").resize(FRAME_SIZE, Image.LANCZOS)


def create_cat_card_frame(number, font):
    img = Image.new("RGB", FRAME_SIZE, CARD_COLOR)
    draw = ImageDraw.Draw(img)
    text = f"Cat #{number}"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (FRAME_SIZE[0] - text_w) // 2
    y = (FRAME_SIZE[1] - text_h) // 2
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    draw.text((x, y), text, fill=TEXT_COLOR, font=font)
    return img


def darken(img, factor):
    return ImageEnhance.Brightness(img).enhance(factor)


def get_sorted_photos():
    photos = [f for f in os.listdir(VERIFIED_DIR) if f.endswith(".jpg")]
    if os.path.exists(VERIFIED_CATS_FILE):
        try:
            with open(VERIFIED_CATS_FILE, "r", encoding="utf-8") as f:
                verified_cats = json.load(f)
            photos.sort(key=lambda name: verified_cats.get(name, {}).get("chonk_score", 0.0), reverse=True)
        except Exception:
            photos.sort()
    else:
        photos.sort()
    return photos[:MAX_PHOTOS]


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)

    if not os.path.exists(VERIFIED_DIR):
        print(f"Error: {VERIFIED_DIR} not found.")
        sys.exit(1)

    photos = get_sorted_photos()
    if not photos:
        print(f"No photos found in {VERIFIED_DIR}")
        sys.exit(1)

    frames_per_item = HOLD_FRAMES + FADE_FRAMES + HOLD_FRAMES + FADE_FRAMES
    total_frames = len(photos) * frames_per_item

    print(f"Generating frames for {len(photos)} cats (~{total_frames} total frames at {FPS} FPS)...")

    # Clear old frames
    for f in os.listdir(FRAMES_DIR):
        if f.endswith(".png"):
            os.remove(os.path.join(FRAMES_DIR, f))

    font = get_font(14)
    frame_idx = 1

    for i, photo_file in enumerate(photos):
        number = len(photos) - i
        photo_path = os.path.join(VERIFIED_DIR, photo_file)
        photo_img = create_photo_frame(photo_path)
        card_img = create_cat_card_frame(number, font)

        # Photo hold
        for _ in range(HOLD_FRAMES):
            photo_img.save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Fade photo to black
        for step in range(FADE_FRAMES):
            factor = 1.0 - (step / FADE_FRAMES)
            darken(photo_img, factor).save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Fade in cat card
        for step in range(FADE_FRAMES):
            factor = step / FADE_FRAMES
            darken(card_img, factor).save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Card hold
        for _ in range(HOLD_FRAMES - FADE_FRAMES):
            card_img.save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        if (i + 1) % 100 == 0:
            print(f"[{i+1}/{len(photos)}] Frame: {frame_idx - 1}")

    print(f"Done. Generated {frame_idx - 1} frames.")


if __name__ == "__main__":
    main()
