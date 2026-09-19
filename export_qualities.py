import os
import sys
import shutil
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SOURCE_FILE = os.path.join(OUTPUT_DIR, "10000_cheese.mp4")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

PRESETS = {
    "compact": {
        "filename": "cheese-top8000-compact-50mb.mp4",
        "crf": "42",
        "preset": "veryfast",
        "desc": "Ultra-compact build (~50MB)"
    },
    "standard": {
        "filename": "cheese-top8000-standard-100mb.mp4",
        "crf": "37",
        "preset": "veryfast",
        "desc": "Standard balance (~100MB)"
    },
    "full": {
        "filename": "cheese-top8000-full-200mb.mp4",
        "desc": "Original high quality (~217MB)"
    }
}


def create_preview():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    gif_path = os.path.join(ASSETS_DIR, "preview.gif")
    print("Generating 15s preview gif...")

    cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:10", "-t", "15",
        "-i", SOURCE_FILE,
        "-vf", "fps=10,scale=256:256:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        gif_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
    if res.returncode == 0:
        print(f"Preview generated at: {gif_path}")
    else:
        print("Failed to generate preview gif.")


def export_preset(name):
    if not os.path.exists(SOURCE_FILE):
        print(f"Error: Base video not found at {SOURCE_FILE}")
        sys.exit(1)

    cfg = PRESETS[name]
    dest = os.path.join(OUTPUT_DIR, cfg["filename"])

    if name == "full":
        print(f"Exporting {name} ({cfg['desc']})...")
        shutil.copy2(SOURCE_FILE, dest)
        print(f"Created: {dest}")
        return

    print(f"Transcoding {name} ({cfg['desc']})...")
    cmd = [
        "ffmpeg", "-y",
        "-i", SOURCE_FILE,
        "-c:v", "libx264",
        "-crf", cfg["crf"],
        "-preset", cfg["preset"],
        "-pix_fmt", "yuv420p",
        dest
    ]
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"Success: {dest} ({mb:.1f} MB)")
    else:
        print(f"Failed to export {name}")


def main():
    parser = argparse.ArgumentParser(description="Export release tiers and preview.")
    parser.add_argument("--preset", choices=["compact", "standard", "full", "all"], default="all")
    parser.add_argument("--preview", action="store_true", help="Only generate preview gif")
    args = parser.parse_args()

    if args.preview:
        create_preview()
        return

    if args.preset == "all":
        create_preview()
        for p in ["compact", "standard", "full"]:
            export_preset(p)
    else:
        export_preset(args.preset)


if __name__ == "__main__":
    main()
