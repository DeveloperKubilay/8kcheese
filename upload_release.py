import os
import sys
import subprocess
import requests
import ssl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
REPO = "DeveloperKubilay/8kcheese"
TAG_NAME = "v2.0.0-cats"
TARGET_BRANCH = "cats"
RELEASE_NAME = "Top 10,000 Cats - Initial Release (v2.0.0)"
RELEASE_BODY = """## 🐱 Top 10,000 Cats (7,752 Verified Cats)

An automated countdown video featuring 7,752 AI-verified cats sorted by chonkiness (fat cats first!), transitioning through classic blue countdown screens and smooth cross-dissolves.

### 📦 Available Video Tiers:
- **cats-100mb.mp4** (~107 MB): Balanced 15-hour countdown for everyday playback.
- **cats-50mb.mp4** (~46 MB): Ultra-compact build.
- **cats-full.mp4** (~181 MB): Master render quality.
- **preview.gif** (~1.8 MB): 15-second animated preview sample.

Verified with local YOLOv8n object detection (100% real cats guarantee).
"""

FILES_TO_UPLOAD = [
    os.path.join(OUTPUT_DIR, "cats-100mb.mp4"),
    os.path.join(OUTPUT_DIR, "cats-50mb.mp4"),
    os.path.join(OUTPUT_DIR, "cats-full.mp4"),
    os.path.join(ASSETS_DIR, "preview.gif")
]


def get_github_token():
    try:
        p = subprocess.Popen(
            ["git", "credential", "fill"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        out, _ = p.communicate(input="protocol=https\nhost=github.com\n\n")
        creds = dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)
        token = creds.get("password")
        if token and (token.startswith("gho_") or token.startswith("ghp_")):
            return token
    except Exception as e:
        print(f"Error fetching credentials: {e}")
    return None


def main():
    token = get_github_token()
    if not token:
        print("Error: Could not retrieve GitHub token from Git Credential Manager.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ClaudeCode-ReleaseUploader"
    }

    print(f"Creating release '{TAG_NAME}' on {REPO} (branch: {TARGET_BRANCH})...")
    create_url = f"https://api.github.com/repos/{REPO}/releases"
    payload = {
        "tag_name": TAG_NAME,
        "target_commitish": TARGET_BRANCH,
        "name": RELEASE_NAME,
        "body": RELEASE_BODY,
        "draft": False,
        "prerelease": False
    }

    # Check if release already exists
    get_rel_url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG_NAME}"
    r_get = requests.get(get_rel_url, headers=headers)
    if r_get.status_code == 200:
        release = r_get.json()
        print(f"Release already exists with ID: {release['id']}")
    else:
        r_create = requests.post(create_url, headers=headers, json=payload)
        if r_create.status_code not in (200, 201):
            print(f"Failed to create release: {r_create.status_code} {r_create.text}")
            sys.exit(1)
        release = r_create.json()
        print(f"Successfully created release ID: {release['id']}")

    upload_url_base = release["upload_url"].split("{")[0]
    existing_assets = {a["name"]: a["id"] for a in release.get("assets", [])}

    for file_path in FILES_TO_UPLOAD:
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            continue

        filename = os.path.basename(file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if filename in existing_assets:
            print(f"Skipping {filename} (already uploaded with asset ID {existing_assets[filename]})")
            continue

        print(f"Uploading {filename} ({file_size_mb:.1f} MB)...")
        upload_url = f"{upload_url_base}?name={filename}"
        content_type = "video/mp4" if filename.endswith(".mp4") else "image/gif"
        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "User-Agent": "ClaudeCode-ReleaseUploader"
        }

        with open(file_path, "rb") as f:
            r_up = requests.post(upload_url, headers=up_headers, data=f)

        if r_up.status_code in (200, 201):
            print(f"SUCCESS: Uploaded {filename}")
        else:
            print(f"FAILED to upload {filename}: {r_up.status_code} {r_up.text}")

    print("\nAll assets processed! Release URL:")
    print(release.get("html_url", f"https://github.com/{REPO}/releases/tag/{TAG_NAME}"))


if __name__ == "__main__":
    main()
