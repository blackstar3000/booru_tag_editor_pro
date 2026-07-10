# ui/prompt_builder.py
"""
Prompt Builder – build a prompt by selecting tags from categorized sections.
"""

import json
from collections import defaultdict
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QListWidget, QListWidgetItem, QLineEdit, QComboBox, QCheckBox,
    QSplitter, QMenu
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QClipboard, QGuiApplication
from core.danbooru_tag_db import DanbooruTagDB
from ui.tag_autocomplete import TagAutocompletePopup, TagEntry
import logging

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    "Quality", "Character", "Copyright", "Artist", "Style",
    "Appearance", "Expression", "Clothing", "Accessories",
    "Pose", "Camera", "Lighting", "Environment", "Effects",
    "Meta", "Uncategorized"
]

DEFAULT_ORDER = [
    "Quality", "Character", "Copyright", "Artist", "Style",
    "Appearance", "Expression", "Clothing", "Accessories",
    "Pose", "Camera", "Lighting", "Environment", "Effects",
    "Meta", "Uncategorized"
]

GENERAL_KEYWORD_MAP = {
    "Quality": [
        "masterpiece", "best quality", "highres", "ultra detailed",
        "high quality", "highly detailed", "detailed", "perfect",
        "beautiful", "gorgeous", "stunning", "magnificent",
        "hq", "hd", "8k", "4k", "sharp focus", "professional",
    ],
    "Style": [
        "watercolor", "sketch", "lineart", "anime style", "realistic",
        "semi-realistic", "chibi", "pixel art", "3d render", "cgi",
        "oil painting", "digital painting", "illustration", "artwork",
        "cell shade", "cel shade", "flat color", "monochrome",
        "grayscale", "ink", "marker", "pastel", "vibrant",
    ],
    "Expression": [
        "smile", "blush", "frown", "angry", "happy", "sad", "crying",
        "laugh", "laughing", "grin", "serious", "surprised", "shock",
        "scared", "fear", "embarrassed", "shy", "confident", "wink",
        "tongue out", "pout", "teeth", "face", "facial expression",
        "expression", "look", "stare", "gaze", "eye contact",
    ],
    "Appearance": [
        "long hair", "short hair", "blonde hair", "brown hair",
        "black hair", "white hair", "silver hair", "blue hair",
        "pink hair", "purple hair", "green hair", "red hair",
        "orange hair", "multicolored hair", "hair ornament",
        "ponytail", "twintails", "braid", "bun", "bangs",
        "ahoge", "sidehair", "drill hair", "curly hair",
        "straight hair", "wavy hair", "hairpin", "hair flower",
        "blue eyes", "green eyes", "red eyes", "brown eyes",
        "grey eyes", "purple eyes", "yellow eyes", "golden eyes",
        "heterochromia", "glasses", "sunglasses", "monocle",
        "freckles", "beard", "mustache", "tan", "pale skin",
        "dark skin", "fair skin", "eyebrow", "eyelash",
    ],
    "Clothing": [
        "dress", "skirt", "shirt", "blouse", "pants", "jeans",
        "shorts", "jacket", "coat", "hoodie", "sweater", "vest",
        "hat", "cap", "beret", "crown", "tiara", "headband",
        "ribbon", "bow", "necktie", "scarf", "gloves", "mittens",
        "socks", "stockings", "pantyhose", "thighhighs", "tights",
        "shoes", "boots", "sandal", "loafers", "heels",
        "uniform", "suit", "armor", "robe", "kimono", "yukata",
        "swimsuit", "bikini", "one-piece", "underwear", "lingerie",
        "bra", "panties", "apron", "cloak", "cape", "belt",
        "necklace", "choker", "bracelet", "ring", "earrings",
        "outfit", "clothing", "wear", "gown", "mini skirt",
        "pleated skirt", "sailor uniform", "school uniform",
    ],
    "Accessories": [
        "sword", "katana", "blade", "wand", "staff", "shield",
        "gun", "pistol", "rifle", "bow", "arrow", "knife", "dagger",
        "spear", "lance", "axe", "hammer", "scythe", "whip",
        "book", "grimoire", "scroll", "umbrella", "parasol",
        "mask", "headphones", "headset", "goggles", "camera",
        "phone", "smartphone", "cup", "teacup", "glass", "bottle",
        "food", "fruit", "flower", "bouquet", "bag", "backpack",
        "purse", "jewelry", "instrument", "guitar", "microphone",
        "glasses", "crown", "ribbon", "bell", "wing", "tail",
        "halo", "demon horn", "animal ear", "cat ear",
    ],
    "Pose": [
        "sitting", "standing", "lying", "laying", "laying down",
        "kneeling", "crouching", "squatting", "bending", "leaning",
        "stretching", "jumping", "running", "walking", "dancing",
        "sleeping", "resting", "pointing", "holding", "reaching",
        "crossed arms", "folded hands", "hand up", "hand on hip",
        "arms up", "arms behind", "leg up", "spread legs",
        "pose", "posture", "gesture", "hand gesture", "peace sign",
        "victory sign", "thumbs up", "salute", "bow", "curtsey",
    ],
    "Camera": [
        "close-up", "closeup", "close_up", "dutch angle",
        "aerial view", "bird's eye", "worm's eye", "low angle",
        "high angle", "rear view", "side view", "profile",
        "from behind", "from side", "from above", "from below",
        "straight on", "cowboy shot", "medium shot", "wide shot",
        "full body", "upper body", "lower body", "face focus",
        "portrait", "headshot", "pov", "first person",
        "overhead", "over-the-shoulder",
    ],
    "Lighting": [
        "backlight", "back light", "rim light", "glow", "glowing",
        "neon", "neon light", "dark", "bright", "sunlight",
        "moonlight", "candlelight", "lamp", "flash", "strobe",
        "volumetric", "god rays", "crepuscular", "soft light",
        "hard light", "diffuse", "ambient", "studio light",
        "cinematic", "dramatic", "moody", "shadow", "shade",
        "silhouette", "highlight", "reflection",
    ],
    "Environment": [
        "sky", "cloud", "sunset", "sunrise", "night", "day",
        "sea", "ocean", "lake", "river", "water", "beach",
        "shore", "coast", "forest", "woods", "tree", "mountain",
        "hill", "field", "grass", "flower", "garden", "park",
        "city", "town", "village", "street", "road", "path",
        "building", "house", "castle", "ruin", "temple", "church",
        "room", "bedroom", "kitchen", "bathroom", "classroom",
        "office", "library", "stage", "balcony", "rooftop",
        "desert", "snow", "ice", "winter", "summer", "spring",
        "autumn", "fall", "rain", "storm", "lightning", "thunder",
        "wind", "fog", "mist", "smoke", "fire", "flame",
        "space", "star", "moon", "planet", "underwater",
        "indoor", "outdoor", "nature", "urban", "countryside",
        "bridge", "fountain", "bench", "stair", "door", "window",
    ],
    "Effects": [
        "blur", "motion blur", "depth of field", "bokeh",
        "particle", "sparkle", "spark", "explosion", "burst",
        "smoke", "fog effect", "mist effect", "steam", "bubble",
        "glitter", "aura", "halo effect", "lens flare",
        "sunflare", "light rays", "light shaft", "shadow",
        "grain", "film grain", "noise", "vignette",
        "chromatic aberration", "splash", "blood", "sweat",
        "tear", "teardrop", "petal", "leaf", "sakura",
        "confetti", "rainbow", "starburst", "glint",
    ],
}


class PromptBuilder(QWidget):
    prompt_changed = pyqtSignal(str)
    seed_requested = pyqtSignal()
    grouping_completed = pyqtSignal(str)

    def __init__(self, danbooru_client=None, tag_db: DanbooruTagDB = None, parent=None):
        super().__init__(parent)
        self.danbooru_client = danbooru_client
        self.tag_db = tag_db
        self.categories = {}
        self.category_order = DEFAULT_ORDER.copy()
        self._autocomplete_connected = False
        self.setup_ui()
        self.load_categories()
        if self.danbooru_client:
            self.setup_autocomplete()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        top_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItems(self.category_order)
        top_row.addWidget(self.category_combo)

        self.add_tag_input = QLineEdit()
        self.add_tag_input.setPlaceholderText("Add tag...")
        self.add_tag_input.returnPressed.connect(self._add_tag_to_category)
        top_row.addWidget(self.add_tag_input)

        self.add_tag_btn = QPushButton("Add")
        self.add_tag_btn.clicked.connect(self._add_tag_to_category)
        top_row.addWidget(self.add_tag_btn)

        left_layout.addLayout(top_row)

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.tag_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self._show_tag_context_menu)
        self.tag_list.itemDoubleClicked.connect(self._remove_selected_tags)
        left_layout.addWidget(self.tag_list)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_selected_tags)
        btn_row.addWidget(self.remove_btn)

        self.clear_cat_btn = QPushButton("Clear Category")
        self.clear_cat_btn.clicked.connect(self._clear_category)
        btn_row.addWidget(self.clear_cat_btn)

        btn_row.addStretch()
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        fmt_row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Comma Separated", "Multi-Line", "Grouped by Category", "Compact"])
        self.format_combo.currentIndexChanged.connect(self.update_preview)
        fmt_row.addWidget(QLabel("Format:"))
        fmt_row.addWidget(self.format_combo)

        self.include_negative = QCheckBox("Include Negative Prompt")
        self.include_negative.setChecked(False)
        self.include_negative.toggled.connect(self.update_preview)
        fmt_row.addWidget(self.include_negative)

        fmt_row.addStretch()
        right_layout.addLayout(fmt_row)

        self.preview_label = QLabel("Prompt Preview:")
        right_layout.addWidget(self.preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select categories and tags to build your prompt...")
        right_layout.addWidget(self.preview_text)

        self.stats_label = QLabel("Tags: 0 | Categories: 0 | Tokens: 0")
        right_layout.addWidget(self.stats_label)

        action_row = QHBoxLayout()
        self.copy_btn = QPushButton("📋 Copy Prompt")
        self.copy_btn.clicked.connect(self.copy_prompt)
        action_row.addWidget(self.copy_btn)

        self.apply_btn = QPushButton("🏷️ Apply to Tags")
        self.apply_btn.clicked.connect(self.apply_to_tags)
        action_row.addWidget(self.apply_btn)

        self.clear_all_btn = QPushButton("🗑️ Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all)
        action_row.addWidget(self.clear_all_btn)

        self.seed_btn = QPushButton("🌱 Send from Image Tags")
        self.seed_btn.clicked.connect(self.seed_requested.emit)
        action_row.addWidget(self.seed_btn)

        action_row.addStretch()
        right_layout.addLayout(action_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        self._on_category_changed()

    def setup_autocomplete(self):
        self._autocomplete_popup = TagAutocompletePopup(self)
        self._autocomplete_popup.install_on(self.add_tag_input)
        self._autocomplete_popup.tag_selected.connect(self._on_tag_selected)
        self.add_tag_input.textChanged.connect(self._on_text_changed_for_autocomplete)

    def _on_tag_selected(self, tag):
        self.add_tag_input.setText(tag)
        self._add_tag_to_category()

    def _on_text_changed_for_autocomplete(self, text):
        if len(text) < 1:
            self._autocomplete_popup.hide()
            return
        results = self.tag_db.search(text) if self.tag_db and self.tag_db.is_loaded else []
        anchor = self.add_tag_input.geometry()
        global_point = self.add_tag_input.parentWidget().mapToGlobal(
            anchor.bottomLeft()) if self.add_tag_input.parentWidget() else \
            self.add_tag_input.mapToGlobal(anchor.bottomLeft())
        api_rect = QRect(global_point, anchor.size())
        api_rect.setHeight(0)
        if results:
            self._autocomplete_popup.show_suggestions(
                [TagEntry(r['name'], r['category'], r['post_count'], source='db') for r in results],
                api_rect
            )
        else:
            self._autocomplete_popup.hide()
        if self.danbooru_client:
            if not self._autocomplete_connected:
                self.danbooru_client.autocomplete_results.connect(self._on_autocomplete_results)
                self.danbooru_client.autocomplete_error.connect(lambda q, e: logger.warning(f"Autocomplete error for '{q}': {e}"))
                self._autocomplete_connected = True
            self.danbooru_client.autocomplete(text)

    def _on_autocomplete_results(self, query, tags):
        if not self.add_tag_input.text().startswith(query):
            return
        if not tags:
            return
        db_results = self.tag_db.search(self.add_tag_input.text()) if self.tag_db and self.tag_db.is_loaded else []
        seen = {r['name'] for r in db_results}
        merged = [TagEntry(r['name'], r['category'], r['post_count'], source='db') for r in db_results]
        for t in tags:
            name = t['name'] if isinstance(t, dict) else t
            if name not in seen:
                if isinstance(t, dict):
                    merged.append(TagEntry(t['name'], t.get('category', 0), t.get('post_count', 0)))
                else:
                    merged.append(TagEntry(t))
                seen.add(name)
        anchor = self.add_tag_input.geometry()
        global_point = self.add_tag_input.parentWidget().mapToGlobal(
            anchor.bottomLeft()) if self.add_tag_input.parentWidget() else \
            self.add_tag_input.mapToGlobal(anchor.bottomLeft())
        api_rect = QRect(global_point, anchor.size())
        api_rect.setHeight(0)
        self._autocomplete_popup.show_suggestions(merged, api_rect)

    def _on_category_changed(self):
        current_cat = self.category_combo.currentText()
        self.tag_list.clear()
        if current_cat in self.categories:
            for tag in self.categories[current_cat]:
                item = QListWidgetItem(tag)
                self.tag_list.addItem(item)

    def _add_tag_to_category(self):
        tag = self.add_tag_input.text().strip()
        if not tag:
            return
        current_cat = self.category_combo.currentText()
        if current_cat not in self.categories:
            self.categories[current_cat] = []
        if tag not in self.categories[current_cat]:
            self.categories[current_cat].append(tag)
            self.add_tag_input.clear()
            self._on_category_changed()
            self.update_preview()
            self._save_categories()

    def _show_tag_context_menu(self, pos):
        item = self.tag_list.itemAt(pos)
        if not item:
            return
        selected = self.tag_list.selectedItems()
        if not selected or item not in selected:
            selected = [item]
        tags = [it.text() for it in selected]
        current_cat = self.category_combo.currentText()
        menu = QMenu()
        label = f"Move {len(tags)} Selected to" if len(tags) > 1 else "Move to"
        move_menu = menu.addMenu(label)
        for cat in self.category_order:
            if cat == current_cat:
                continue
            act = move_menu.addAction(cat)
            act.setData(cat)
        move_menu.triggered.connect(lambda act: self._move_tags(tags, current_cat, act.data()))
        menu.addSeparator()
        remove_label = f"Remove {len(tags)} Selected" if len(tags) > 1 else "Remove"
        remove_act = menu.addAction(remove_label)
        remove_act.triggered.connect(lambda: self._remove_single_tags(tags, current_cat))
        menu.exec_(self.tag_list.mapToGlobal(pos))

    def _move_tags(self, tags, from_cat, to_cat):
        moved = 0
        for tag in tags:
            if from_cat in self.categories and tag in self.categories[from_cat]:
                self.categories[from_cat].remove(tag)
                moved += 1
        if to_cat not in self.categories:
            self.categories[to_cat] = []
        for tag in tags:
            if tag not in self.categories[to_cat]:
                self.categories[to_cat].append(tag)
        if moved:
            self._on_category_changed()
            self.update_preview()
            self._save_categories()

    def _remove_single_tags(self, tags, from_cat):
        if from_cat in self.categories:
            self.categories[from_cat] = [t for t in self.categories[from_cat] if t not in tags]
            self._on_category_changed()
            self.update_preview()
            self._save_categories()

    def _remove_selected_tags(self):
        current_cat = self.category_combo.currentText()
        selected = self.tag_list.selectedItems()
        if selected:
            to_remove = [item.text() for item in selected]
            if current_cat in self.categories:
                self.categories[current_cat] = [t for t in self.categories[current_cat] if t not in to_remove]
                self._on_category_changed()
                self.update_preview()
                self._save_categories()

    def _clear_category(self):
        current_cat = self.category_combo.currentText()
        if current_cat in self.categories and self.categories[current_cat]:
            if QMessageBox.question(self, "Clear Category", f"Clear all tags in '{current_cat}'?") == QMessageBox.Yes:
                self.categories[current_cat].clear()
                self._on_category_changed()
                self.update_preview()
                self._save_categories()

    def clear_all(self):
        if QMessageBox.question(self, "Clear All", "Clear all tags from all categories?") == QMessageBox.Yes:
            for cat in self.categories:
                self.categories[cat].clear()
            self._on_category_changed()
            self.update_preview()
            self._save_categories()

    def load_categories(self):
        json_path = Path(__file__).parent.parent / "prompt_categories.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.categories = data.get('categories', {})
                self.category_order = data.get('order', DEFAULT_ORDER)
                logger.info(f"Loaded prompt categories from {json_path}")
            except Exception as e:
                logger.warning(f"Failed to load prompt categories: {e}")
                self._create_defaults()
        else:
            self._create_defaults()
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({'categories': self.categories, 'order': self.category_order}, f, indent=2)
                logger.info(f"Saved default prompt categories to {json_path}")
            except:
                pass

        self.category_combo.clear()
        self.category_combo.addItems(self.category_order)
        self._on_category_changed()

    def _save_categories(self):
        json_path = Path(__file__).parent.parent / "prompt_categories.json"
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({'categories': self.categories, 'order': self.category_order}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save prompt categories: {e}")

    def _create_defaults(self):
        self.categories = {cat: [] for cat in DEFAULT_CATEGORIES}
        self.category_order = DEFAULT_ORDER.copy()

    def _get_tag_category(self, tag: str):
        """Look up a tag's Danbooru category from the tag DB."""
        if not self.tag_db or not self.tag_db.is_loaded:
            return None
        results = self.tag_db.search(tag, limit=1)
        if results and results[0]['name'].lower() == tag.lower():
            return results[0].get('category', 0)
        return None

    def _classify_general(self, tag_name: str):
        """Classify a general (category 0) tag into a sub-category using keyword scoring."""
        name = tag_name.lower().replace('_', ' ').replace('-', ' ')

        best_cat = None
        best_score = 0

        for section, keywords in GENERAL_KEYWORD_MAP.items():
            score = 0
            for kw in keywords:
                if kw in name:
                    score += len(kw)
            if score > best_score:
                best_score = score
                best_cat = section

        return best_cat if best_score > 0 else None

    def seed_from_tags(self, tags):
        for cat in self.categories:
            self.categories[cat].clear()
        for cat in self.category_order:
            if cat not in self.categories:
                self.categories[cat] = []

        stats = defaultdict(int)

        for tag in tags:
            db_cat = self._get_tag_category(tag)
            target = None

            if db_cat == 1:
                target = "Artist"
            elif db_cat == 3:
                target = "Copyright"
            elif db_cat == 4:
                target = "Character"
            elif db_cat == 5:
                target = "Meta"
            else:
                target = self._classify_general(tag)
                if target is None:
                    target = "Uncategorized"

            if target in self.categories:
                self.categories[target].append(tag)
            else:
                self.categories.setdefault("Uncategorized", []).append(tag)
                target = "Uncategorized"
            stats[target] += 1

        imported = len(tags)
        grouped = sum(v for k, v in stats.items() if k != "Uncategorized")
        cat_count = sum(1 for v in stats.values() if v > 0)

        parts = [f"Imported {imported} tags into {cat_count} sections"]
        if grouped:
            parts.append(f"{grouped} classified")
        if stats.get("Uncategorized", 0):
            parts.append(f"{stats['Uncategorized']} unclassified")
        self.grouping_completed.emit(" \u00b7 ".join(parts))

        self._on_category_changed()
        self.update_preview()
        self._save_categories()
        return imported

    def update_preview(self):
        format_mode = self.format_combo.currentText()
        include_negative = self.include_negative.isChecked()

        ordered = []
        for cat in self.category_order:
            if cat in self.categories and self.categories[cat]:
                ordered.append((cat, self.categories[cat]))

        if format_mode == "Comma Separated":
            all_tags = []
            for cat, tags in ordered:
                all_tags.extend(tags)
            prompt = ", ".join(all_tags)
        elif format_mode == "Multi-Line":
            lines = []
            for cat, tags in ordered:
                lines.extend(tags)
            prompt = "\n".join(lines)
        elif format_mode == "Grouped by Category":
            sections = []
            for cat, tags in ordered:
                sections.append(f"### {cat}")
                sections.extend(tags)
                sections.append("")
            prompt = "\n".join(sections)
        else:  # Compact
            all_tags = []
            for cat, tags in ordered:
                all_tags.extend(tags)
            prompt = ", ".join(all_tags)

        self.preview_text.setText(prompt)
        self.prompt_changed.emit(prompt)

        total_tags = sum(len(tags) for tags in self.categories.values())
        token_estimate = len(prompt) // 4
        self.stats_label.setText(f"Tags: {total_tags} | Categories: {len(self.categories)} | Tokens: {token_estimate}")

    def copy_prompt(self):
        prompt = self.preview_text.toPlainText()
        if prompt:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(prompt)
            logger.info("Prompt copied to clipboard")

    def apply_to_tags(self):
        prompt = self.preview_text.toPlainText()
        if prompt:
            self.prompt_changed.emit(prompt)