import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFIED_DIR = os.path.join(BASE_DIR, "verified")
FRAMES_DIR = os.path.join(BASE_DIR, "frames")
FRAME_SIZE = (128, 128)
BLUE_COLOR = (0, 100, 200)
TEXT_COLOR = (255, 255, 255)
MAX_PHOTOS = 10000

FPS = 15
HOLD_FRAMES = FPS * 3
FADE_FRAMES = FPS * 1


def get_font(size=14):
    candidates = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS
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


def create_blue_frame(number, font):
    img = Image.new("RGB", FRAME_SIZE, BLUE_COLOR)
    draw = ImageDraw.Draw(img)
    text = f"Number: {number}"
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


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)

    photos = sorted([f for f in os.listdir(VERIFIED_DIR) if f.endswith(".jpg")])
    if not photos:
        print(f"No photos found in {VERIFIED_DIR}")
        sys.exit(1)

    photos = photos[:MAX_PHOTOS]
    frames_per_item = HOLD_FRAMES + FADE_FRAMES + HOLD_FRAMES + FADE_FRAMES
    total_frames = len(photos) * frames_per_item

    print(f"Generating frames for {len(photos)} items (~{total_frames} total frames at {FPS} FPS)...")

    # Clear old frames
    for f in os.listdir(FRAMES_DIR):
        if f.endswith(".png"):
            os.remove(os.path.join(FRAMES_DIR, f))

    font = get_font(14)
    frame_idx = 1

    for i, photo_file in enumerate(photos):
        number = i + 1
        photo_path = os.path.join(VERIFIED_DIR, photo_file)
        photo_img = create_photo_frame(photo_path)
        blue_img = create_blue_frame(number, font)

        # Photo hold
        for _ in range(HOLD_FRAMES):
            photo_img.save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Fade photo to black
        for step in range(FADE_FRAMES):
            factor = 1.0 - (step / FADE_FRAMES)
            darken(photo_img, factor).save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Fade in blue card
        for step in range(FADE_FRAMES):
            factor = step / FADE_FRAMES
            darken(blue_img, factor).save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        # Blue card hold
        for _ in range(HOLD_FRAMES - FADE_FRAMES):
            blue_img.save(os.path.join(FRAMES_DIR, f"{frame_idx:07d}.png"))
            frame_idx += 1

        if (i + 1) % 100 == 0:
            print(f"[{i+1}/{len(photos)}] Frame: {frame_idx - 1}")

    print(f"Done. Generated {frame_idx - 1} frames.")


if __name__ == "__main__":
    main()
