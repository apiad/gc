# Machine Learning Framework Cache Signatures

This document outlines the standard cache directory locations, file structures, and management tools for major Machine Learning frameworks. These paths are primary targets for garbage collection to reclaim disk space.

---

## 1. Hugging Face (`huggingface_hub`, `transformers`, `datasets`)

Hugging Face uses a unified caching system to store models, tokenizers, and datasets. It employs a content-addressable storage system with symlinks to support multiple versions efficiently.

### Standard Paths
- **Linux/macOS:** `~/.cache/huggingface/`
- **Windows:** `%USERPROFILE%\.cache\huggingface\`
- **Global Root Env:** `HF_HOME`
- **Model Cache Env:** `HF_HUB_CACHE`
- **Datasets Cache Env:** `HF_DATASETS_CACHE`

### Directory Structure & Glob Patterns
| Component | Path (relative to root) | Description |
| :--- | :--- | :--- |
| **Model Hub** | `hub/` | Root for all models and sub-modules. |
| **Blobs** | `hub/models--<author>--<repo>/blobs/` | Actual binary files (named by SHA). |
| **Snapshots** | `hub/models--<author>--<repo>/snapshots/` | Symlinks to blobs, organized by commit hash. |
| **Datasets** | `datasets/` | Downloaded datasets and processed Arrow files. |
| **Locks** | `hub/.locks/` | Directory containing lock files for concurrent downloads. |

### Junk & Safe-to-Delete Files
- **Lock Files:** `hub/.locks/**/*.lock` (Safe to delete if no active process is running).
- **Incomplete Downloads:** `hub/**/blobs/*.incomplete` (Safe to delete).
- **Stale Snapshots:** Snapshots for old versions of a model can be deleted, but it is recommended to use the CLI.

### Impact of Deletion
- **Regenerability:** Models and datasets are fully regenerable by re-downloading.
- **Cost:** High. Large language models (LLMs) can range from 10GB to 100GB+. Re-downloading incurs significant bandwidth and time.

### Management Tools
- **Scan Cache:** `huggingface-cli scan-cache`
- **Delete Cache (Interactive):** `huggingface-cli delete-cache`
- **Programmatic (Datasets):** `dataset.cleanup_cache_files()`

---

## 2. PyTorch (`torch.hub`)

PyTorch Hub stores pre-trained model weights and Git repositories for easy loading.

### Standard Paths
- **Default:** `~/.cache/torch/hub/`
- **Checkpoints:** `~/.cache/torch/hub/checkpoints/`
- **Env Variable:** `TORCH_HOME` (Weights stored in `$TORCH_HOME/hub`)
- **XDG Fallback:** `$XDG_CACHE_HOME/torch/hub`

### Directory Structure & Glob Patterns
- **Checkpoints:** `checkpoints/*.pth`, `checkpoints/*.pt`
- **Partial Downloads:** `checkpoints/*.{uuid}.partial`
- **Lock Files:** `checkpoints/*.lock`

### Junk & Safe-to-Delete Files
- **Partial Downloads:** `**/*.partial` (Safe to delete if no active download).
- **Lock Files:** `**/*.lock` (Safe to delete if no active download).

### Impact of Deletion
- **Regenerability:** Fully regenerable via `torch.hub.load`.
- **Cost:** Moderate. Vision models are usually <500MB; specialized models can be several GBs.

### Management Tools
- **Programmatic Access:** `torch.hub.get_dir()` and `torch.hub.set_dir('path')`.
- **Force Update:** `torch.hub.load(..., force_reload=True)`.

---

## 3. TensorFlow Hub (`tensorflow_hub`)

TensorFlow Hub caches modules (models) in a decompressed format.

### Standard Paths
- **Default (Non-persistent):** `/tmp/tfhub_modules`
- **Persistent Env:** `TFHUB_CACHE_DIR` (Highly recommended to avoid re-downloads).

### Directory Structure & Glob Patterns
Models are stored in directories named after the SHA-1 hash of their download URL.
- **Hashed Folder:** `<hash>/` (Contains `saved_model.pb`, `variables/`, `assets/`).
- **Completion Marker:** `<hash>.descriptor.txt` (Presence indicates a successful download).
- **Lock Files:** `<hash>.lock`
- **Temporary Files:** `*.tmp` or directories inside the hashed folder.

### Junk & Safe-to-Delete Files
- **Stale Locks:** `<hash>.lock` (If a download hangs, delete this and the corresponding folder).
- **Partial Folders:** Any directory without a corresponding `.descriptor.txt` is likely incomplete.

### Impact of Deletion
- **Regenerability:** Fully regenerable.
- **Cost:** Moderate to High. Some TF modules (like BERT or Universal Sentence Encoder) are large.

### Management Tools
- **No official CLI:** Management is purely manual (file deletion).

---

## 4. Kaggle (`kaggle`, `kagglehub`)

Kaggle provides two main ways to download data: the legacy CLI and the modern `kagglehub` library.

### Standard Paths
- **KaggleHub Cache:** `~/.cache/kagglehub/`
- **KaggleHub Env:** `KAGGLEHUB_CACHE`
- **Kaggle Config:** `~/.kaggle/` (Contains `kaggle.json` credentials).
- **CLI Downloads:** Default to the current working directory.

### Directory Structure & Glob Patterns
- **Datasets:** `datasets/<author>/<dataset-name>/<version>/`
- **Models:** `models/<author>/<model-name>/<framework>/<variation>/<version>/`
- **Lock Files:** `**/*.lock` (Created via the `filelock` package).
- **Temp Files:** `**/*.tmp`

### Junk & Safe-to-Delete Files
- **Lock Files:** `**/*.lock` (Safe if no active `kagglehub` process).
- **Temporary Files:** `**/*.tmp` (Leftovers from interrupted downloads/extractions).

### Impact of Deletion
- **Regenerability:** Fully regenerable.
- **Cost:** High for datasets. Kaggle datasets often reach dozens of GBs.

### Management Tools
- **Kaggle CLI Path Config:** `kaggle config set -n path -v /path/to/dir`
- **KaggleHub:** No built-in cleanup CLI; manual deletion required.

---

## Summary of Cleanup Signatures

| Framework | Root Path | Lock/Temp Pattern | Completion Marker |
| :--- | :--- | :--- | :--- |
| **Hugging Face** | `~/.cache/huggingface` | `**/*.lock`, `**/*.incomplete` | `refs/main` / `snapshots/` |
| **PyTorch** | `~/.cache/torch/hub` | `**/*.lock`, `**/*.partial` | Final `.pth` file |
| **TensorFlow** | `/tmp/tfhub_modules` | `*.lock`, `*.tmp` | `<hash>.descriptor.txt` |
| **Kaggle** | `~/.cache/kagglehub` | `**/*.lock`, `**/*.tmp` | Final versioned folder |
