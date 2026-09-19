import os
import sys
import time
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("download", "downloader.py", "Download Images"),
    ("classify", "classifier.py", "Verify & Filter Images"),
    ("frames", "frame_builder.py", "Build Animation Frames"),
    ("video", "video_builder.py", "Render & Concatenate Video"),
]


def run_step(script_name, label):
    path = os.path.join(BASE_DIR, script_name)
    print(f"\n--- [{label}] Starting {script_name} ---")
    start = time.time()

    res = subprocess.run([sys.executable, path], cwd=BASE_DIR)
    elapsed = time.time() - start

    if res.returncode != 0:
        print(f"FAILED: {label} (after {elapsed:.1f}s)")
        return False

    print(f"PASSED: {label} ({elapsed:.1f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the cheese video generation pipeline.")
    parser.add_argument("--skip-download", action="store_true", help="Skip image downloading")
    parser.add_argument("--skip-classify", action="store_true", help="Skip classification/verification")
    parser.add_argument("--skip-frames", action="store_true", help="Skip frame generation")
    parser.add_argument("--skip-video", action="store_true", help="Skip video building")
    args = parser.parse_args()

    skip_map = {
        "download": args.skip_download,
        "classify": args.skip_classify,
        "frames": args.skip_frames,
        "video": args.skip_video,
    }

    start_time = time.time()

    for key, script, label in STEPS:
        if skip_map.get(key, False):
            print(f"Skipping step: {label} (--skip-{key})")
            continue

        if not run_step(script, label):
            print(f"\nPipeline halted at stage: {label}")
            sys.exit(1)

    total_time = (time.time() - start_time) / 60
    print(f"\nPipeline completed in {total_time:.1f} minutes.")


if __name__ == "__main__":
    main()
