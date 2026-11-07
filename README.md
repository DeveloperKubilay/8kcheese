# 🍲 Top 10,000 Turkish Foods Video Generator

An automated end-to-end media pipeline powered by **local lightweight AI (Swin Transformer Food-101 via ONNX Runtime)** that downloads, verifies, sorts by appetizing deliciousness, and renders an epic 15+ hour countdown video featuring thousands of verified Turkish dishes (kebabs, baklava, lahmacun, pide, home stews, and street foods).

<p align="center">
  <img src="assets/preview.gif" alt="Turkish Foods Video Preview" width="320" />
</p>

---

## 📦 Quality Tiers & Previews

Compare the visual quality of each compression tier before downloading. All releases feature the complete 15-hour countdown.

| Tier | Size | Bitrate | Preview Sample (15s) | Direct Download |
|---|---|---|:---:|---|
| **Compact** | ~50 MB | ~7 kbps | ![Compact Preview](assets/preview-50mb.gif) | [📥 Download 50MB (MP4)](https://github.com/DeveloperKubilay/8kcheese/releases/download/v3.0.0-turkish-food/turkish-food-50mb.mp4) |
| **Standard** | ~100 MB | ~14 kbps | ![Standard Preview](assets/preview-100mb.gif) | [📥 Download 100MB (MP4)](https://github.com/DeveloperKubilay/8kcheese/releases/download/v3.0.0-turkish-food/turkish-food-100mb.mp4) |
| **Master** | ~180 MB | ~27 kbps | ![Master Preview](assets/preview-full.gif) | [📥 Download 180MB (MP4)](https://github.com/DeveloperKubilay/8kcheese/releases/download/v3.0.0-turkish-food/turkish-food-full.mp4) |

> 🏷️ All versions and release assets can also be browsed at the [v3.0.0-turkish-food Release Page](https://github.com/DeveloperKubilay/8kcheese/releases/tag/v3.0.0-turkish-food).

---

## 🚀 Pipeline Architecture

The pipeline runs in 3 automated stages orchestrated by `run_all.py`:

```
Pexels API ──> [downloader.py] ──> photos/ (Kebabs, Baklava, Pide, Home Dishes...)
                                      │
                                      ▼
                        [classifier.py] (Swin Food-101 ONNX AI)
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
         verified/ (Food Only)                 rejected/ (Non-food filtered)
                   │
                   ▼ (Sorted: Deliciousness score ascending towards #1)
         [video_builder.py] ──> clips/ ──> output/10000_turkish_foods.mp4
                                                 │
                                                 ▼
                                     [export_qualities.py] ──> Releases
```

1. **Downloader (`downloader.py`)**: Fetches candidates across curated authentic Turkish cuisine categories:
   - **Kebabs & Meats**: *Adana kebap, İskender, Şiş kebap, Döner, Çiğ köfte, Cağ kebabı, Beyti, Sac tava, Kuzu tandır, Kokoreç, Hünkar beğendi...*
   - **Baked & Street Food**: *Lahmacun, Pide, Su böreği, Simit, Gözleme, Tantuni, Balık ekmek, Midye dolma, Bazlama, Kumru, Boyoz...*
   - **Home Dishes & Stews**: *Kuru fasulye, Yaprak sarma, Dolma, Karnıyarık, Mantı, Musakka, Güveç, Menemen, İçli köfte...*
   - **Breakfast & Meze**: *Serpme kahvaltı, Şakşuka, Haydari, Humus, Acılı ezme, Bal kaymak, Türk çayı, Türk kahvesi...*
   - **Desserts & Sweets**: *Baklava, Künefe, Kadayıf, Fırın sütlaç, Kazandibi, Lokum, Tulumba, Şekerpare, Maraş dondurması, Helva, Trileçe...*
   - **Soups**: *Mercimek çorbası, Tarhana, Ezogelin, Yayla, İşkembe, Kelle paça...*
2. **AI Classifier (`classifier.py`)**:
   - Uses local **Swin Transformer Food-101 ONNX** running on CPU across all available cores via `ProcessPoolExecutor`.
   - **Guaranteed Real Food**: Strict dual-confidence & logit verification filters out non-food items (cars, buildings, empty landscapes, unrelated portraits).
   - **Flexible Real-Life Context**: Intelligently permits natural dining settings (waiters serving dishes, people dining, banquet tables).
   - **Deliciousness Ranking**: Computes color saturation, warmth, and contrast metrics alongside AI certainty so the most appetizing, mouth-watering dishes build up to the #1 finale.
3. **Video Builder (`video_builder.py`)**:
   - **Classic Blue Screen & Smooth Crossfades**: Generates blue countdown cards displaying `Number: {number}` and the authentic Turkish dish name in warm golden text.
   - Pacing: 1s fade-in, 2s card hold, 1s crossfade dissolve into the verified food photograph, 2s food hold, and 1s fade-out (7.0s per item).
   - Micro-clips are rendered in parallel across all CPU cores and losslessly stitched into `output/10000_turkish_foods.mp4`.
4. **Export Qualities (`export_qualities.py`)**:
   - Transcodes master output into Compact (50MB), Standard (100MB), and Master (180MB) release tiers.

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.9+
- [FFmpeg](https://ffmpeg.org/) installed and available in system `PATH`
- Pexels API Key ([Get a free key here](https://www.pexels.com/api/))

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your API key in `.env`:
   ```bash
   PEXELS_API_KEY="your_api_key_here"
   ```

---

## ⚙️ Running the Pipeline

To run the complete pipeline from scratch:
```bash
python run_all.py
```

To clear previous caches and start a clean run:
```bash
python run_all.py --clean
```

You can skip stages if intermediate assets already exist:
```bash
python run_all.py --skip-download --skip-classify
```

To transcode release tiers:
```bash
python export_qualities.py --preset all
```
