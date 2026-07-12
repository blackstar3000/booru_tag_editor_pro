# 🧊 Booru Tag Editor Pro++

> A modern desktop application for browsing images, editing Booru-style tags, managing AI metadata, and building structured prompts — all in one unified interface.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen.svg)

---

## Overview

**Booru Tag Editor Pro++** is a full-featured prompt editor and dataset manager for AI artists. It combines an image browser, tag editor, prompt builder, metadata viewer, and dataset audit tools into a single glassmorphism-styled interface.

Designed for workflows using **ComfyUI**, **Stable Diffusion**, **SDXL**, **Flux**, **Automatic1111**, **Forge**, and other AI image generation tools.

---

## Features

### Image Browser

- Browse folders containing AI-generated images
- Auto-scaling image viewer with smooth resizing
- Sort by name, date, size, or random order
- Drag-and-drop folder loading
- Auto-load last folder on startup
- File operations: open, reveal in explorer, copy path, rename, delete
- Image context menu with all common actions
- Thumbnail filmstrip with 90×90 previews and hover preview popup
- Filmstrip auto-hide (configurable 5-second timeout with bottom-edge reveal)

### Tag Editor

- Add, remove, reorder tags with drag-and-drop
- Multi-select for bulk operations
- Real-time search/filter across tags
- Autocomplete from Danbooru tag database (500k+ tags)
- Live API autocomplete from Danbooru
- Category-colored tag display (General, Artist, Copyright, Character, Meta)
- Tag Inspector: wiki content, example posts, post counts
- Unlimited undo/redo (30 levels)
- Save tags to `.txt` sidecar files

### Prompt Builder

- 16 categorized tag groups: Quality, Character, Copyright, Artist, Style, Appearance, Expression, Clothing, Accessories, Pose, Camera, Lighting, Environment, Effects, Meta, Uncategorized
- 4 output formats: comma-separated, multi-line, grouped, compact
- Find and replace (plain text or regex)
- Reorder tags dialog with drag-and-drop
- Seed from current image tags with auto-classification
- Live preview with tag count and token estimate
- Per-image prompt builder state (persisted to JSON)

### AI Metadata Viewer

- Reads ComfyUI embedded workflows (node graph walking)
- Reads Automatic1111/Forge/Civitai parameter strings
- Extracts prompt, negative prompt, settings, model, sampler, seed, CFG
- Copy prompt to clipboard
- Import tags from prompt
- Raw metadata toggle

### Text Editor

- Multi-document tabbed interface with file explorer pane
- Syntax highlighting for Python, JavaScript, HTML, CSS, JSON, YAML, Markdown
- Booru tag category highlighting in `.txt` files
- Tag autocomplete popup in tag files
- Find and replace, word wrap, zoom
- Save / Save As / Save All
- Dark title bar (Windows DWM integration)

### Dataset Audit

- Comprehensive scan: missing `.txt` files, orphan files, unknown tags, broken images
- Tag count statistics (min, max, average)
- Resolution and file type distribution
- Top 20 most used tags
- Export report as JSON
- Background scanning with progress bar

### Duplicate Finder

- Perceptual hash-based detection (imagehash)
- Thumbnail grid display of duplicate groups
- Keep Best in Each Group (auto-keeps highest resolution)
- Per-file delete with confirmation

### Smart Tools

- **Smart Collections**: filter images by tag, resolution, file type, date conditions
  - 9 condition types with AND/OR logic
  - Apply collection as filmstrip filter
  - Persisted to `smart_collections.json`
- **Bulk Operations** (12 operations):
  - Add, remove, replace tags
  - Regex find/replace
  - Merge, split, prefix, suffix
  - Sort, normalize, rename
  - Preview mode before applying

### Statistics Dashboard

- Total images, total tags, average tags per image
- Top 10 most common tags
- Resolution distribution
- File type distribution
- Background computation with progress tracking

### Workspaces

- Save and restore complete window layouts (splitters, tabs, panels, filmstrip)
- Rename, duplicate, delete workspaces
- Export/import workspace JSON files
- Set startup workspace
- Auto-hide filmstrip toggle per workspace
- Stored in `settings/workspaces/`

### Glassmorphism Tooltips

- Custom-painted tooltips matching the dark purple theme
- 6 color variants: default, info, success, warning, error, ai
- Rich content: icon, title, description, keyboard shortcut badge
- Fade-in animation (180ms cubic ease-out)
- Smart positioning with pointer arrow
- Per-widget registration with 300ms hover delay

### User Interface

- Dark purple glassmorphism design with translucent panels
- Rounded corners on all panels and controls
- Purple accent colors with soft glow effects
- Dark title bar (Windows 10/11 DWM)
- Styled menu bar, toolbar, tabs, scrollbars, splitters, checkboxes
- Resizable panels with splitter handles
- Keyboard navigation: arrow keys, Delete, Ctrl+S/Z/Y/O/U
- Status bar with image counter, filename, tag count, dirty indicator

---

## Screenshots

### Main Editor

![Main Editor](screenshots/main_editor.png.png)

### Prompt Builder

![Prompt Builder](screenshots/prompt_builder.png)

---

## Installation

### Requirements

- Python 3.10+
- Windows 10/11

### Setup

```bash
git clone https://github.com/blackstar3000/booru_tag_editor_pro.git
cd booru_tag_editor_pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

---

## Project Structure

```
booru_tag_editor_pro/
├── main.py
├── app.py
├── config.py
├── constants.py
├── logging_config.py
├── smart_collections.json
├── prompt_categories.json
│
├── data/
│   ├── danbooru_tags.csv
│   └── danbooru_tags_cooccurrence.csv
│
├── core/
│   ├── advanced_bulk.py
│   ├── ai_metadata_reader.py
│   ├── danbooru_client.py
│   ├── danbooru_tag_db.py
│   ├── duplicate_detector.py
│   ├── image_loader.py
│   ├── image_model.py
│   ├── metadata_reader.py
│   ├── navigation_controller.py
│   ├── settings_manager.py
│   ├── smart_collection.py
│   ├── syntax_highlighter.py
│   ├── tag_highlighter.py
│   ├── tag_manager.py
│   ├── thumbnail_cache.py
│   └── workspace_manager.py
│
├── workers/
│   ├── folder_scan_worker.py
│   ├── metadata_worker.py
│   └── thumbnail_worker.py
│
├── ui/
│   ├── main_window.py
│   ├── glassmorphism_style.py
│   ├── tooltips.py
│   ├── image_viewer.py
│   ├── folder_tree.py
│   ├── filmstrip.py
│   ├── tag_panel.py
│   ├── tag_inspector.py
│   ├── tag_autocomplete.py
│   ├── metadata_panel.py
│   ├── prompt_builder.py
│   ├── text_editor.py
│   ├── statistics_dashboard.py
│   ├── duplicate_finder.py
│   ├── dataset_audit.py
│   ├── smart_tools.py
│   └── dialogs/
│       ├── batch_dialog.py
│       ├── settings_dialog.py
│       ├── workspace_manager_dialog.py
│       └── workspace_save_dialog.py
│
├── settings/
│   └── workspaces/
│
└── logs/
```

---

## Keyboard Shortcuts

| Action         | Shortcut |
| -------------- | -------- |
| Open folder    | `Ctrl+O` |
| Go up          | `Ctrl+U` |
| Previous image | `Left`   |
| Next image     | `Right`  |
| Save           | `Ctrl+S` |
| Undo           | `Ctrl+Z` |
| Redo           | `Ctrl+Y` |
| Delete image   | `Delete` |

---

## Danbooru Integration

The app connects to the Danbooru API for tag autocomplete, tag inspection, and wiki content. To enable API features:

1. Go to **Settings** in the toolbar
2. Enter your Danbooru username and API key
3. Optionally add cookies for Cloudflare bypass

Without credentials, the app uses the local tag database (`data/danbooru_tags.csv`) with 500k+ tags.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
