# 🧀 Top 8000 Cheese Video Generator

An automated end-to-end media pipeline that downloads, verifies, formats, and renders an epic 15+ hour countdown video featuring thousands of unique cheeses.

<p align="center">
  <img src="assets/preview.gif" alt="Cheese Video Preview" width="320" />
</p>

---

## 📦 Downloads (GitHub Releases)

Because Git repositories have strict file size limits, the final rendered videos are distributed via [GitHub Releases](../../releases). Choose the version that best fits your bandwidth and storage:

| Tier | File Size | Bitrate / Description | Download |
|---|---|---|---|
| **Compact** | ~50 MB | Optimized 480p equivalent, lowest bandwidth | [Download 50MB](../../releases/latest) |
| **Standard** | ~100 MB | Balanced quality for everyday playback | [Download 100MB](../../releases/latest) |
| **Full / Original** | ~217 MB | Full original master render (15.6 hours) | [Download 217MB](../../releases/latest) |

---

## 🚀 Pipeline Architecture

The project runs in 4 sequential stages orchestrated by `run_all.py`:

```
Pexels API ──> [downloader.py] ──> photos/
                                      │
                                      ▼
                               [classifier.py] ──> verified/
                                      │
                                      ▼
                              [video_builder.py] ──> clips/ ──> output/10000_cheese.mp4
                                                                     │
                                                                     ▼
                                                          [export_qualities.py] ──> Releases
```

1. **Downloader (`downloader.py`)**: Fetches thousands of unique cheese photos concurrently using the Pexels API with automatic rate-limit backoff.
2. **Classifier (`classifier.py`)**: Validates image headers and dimensions, filtering out broken or tiny assets.
3. **Video Builder (`video_builder.py`)**: Generates blue transition count cards and produces micro-clips with smooth cross-dissolve transitions using FFmpeg.
4. **Export Qualities (`export_qualities.py`)**: Transcodes master outputs into compact (50MB), standard (100MB), and full (200MB) release artifacts.

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.9+
- [FFmpeg](https://ffmpeg.org/) installed and available in your system `PATH`
- Pexels API Key ([Get a free key here](https://www.pexels.com/api/))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/DeveloperKubilay/8kcheese.git
   cd 8kcheese
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API key:
   ```bash
   cp .env.example .env
   # Edit .env and insert your PEXELS_API_KEY
   ```
   Or export it in your shell:
   ```bash
   export PEXELS_API_KEY="your_api_key_here"
   ```

---

## ⚙️ Running the Pipeline

To run the complete pipeline from scratch:
```bash
python run_all.py
```

You can skip stages if intermediate assets already exist:
```bash
python run_all.py --skip-download --skip-classify
```

To transcode release tiers and generate preview assets:
```bash
python export_qualities.py --preset all
```

---

## 🤖 GitHub Actions CI/CD

When a tag is pushed (e.g., `git tag v1.0.0 && git push origin v1.0.0`), the included `.github/workflows/release.yml` workflow automatically sets up the environment and publishes all video tiers to GitHub Releases.

Make sure to add `PEXELS_API_KEY` to your **Repository Secrets** if you want automated pipeline builds in GitHub Actions.

---

## 📄 License
MIT
