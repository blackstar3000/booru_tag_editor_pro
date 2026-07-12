from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel,
    QLineEdit, QPushButton, QMenu, QAction, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from core.tag_manager import TagManager
from core.booru_source_manager import BooruSourceManager
from core.danbooru_tag_db import DanbooruTagDB
from ui.tag_inspector import TagInspector
from ui.tag_autocomplete import TagAutocompletePopup, TagEntry
import logging

logger = logging.getLogger(__name__)

class TagListWidget(QListWidget):
    orderChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        new_order = [self.item(i).text() for i in range(self.count())]
        self.orderChanged.emit(new_order)


class TagPanel(QWidget):
    tags_changed = pyqtSignal(list)

    def __init__(self, tag_manager: TagManager, source_manager: BooruSourceManager = None, tag_db: DanbooruTagDB = None, parent=None):
        super().__init__(parent)
        self.tag_manager = tag_manager
        self.source_manager = source_manager
        self.tag_db = tag_db
        self.all_tags = []
        self.filter_text = ""
        self.inspector = None
        self._current_inspected_tag = None
        self.setup_ui()
        self.tag_manager.tags_changed.connect(self._on_tags_changed)
        if self.source_manager:
            self.source_manager.autocomplete_results.connect(self._on_autocomplete_results)
            self.source_manager.autocomplete_error.connect(lambda q, e: logger.warning(f"Autocomplete error for '{q}': {e}"))
            self.source_manager.tag_info_fetched.connect(self._on_tag_info_fetched)
            self.source_manager.tag_info_error.connect(self._on_tag_info_error)
            self.source_manager.wiki_fetched.connect(self._on_wiki_fetched)
            self.source_manager.example_posts_fetched.connect(self._on_example_posts_fetched)
            self.source_manager.preview_loaded.connect(self._on_preview_loaded)
            self.source_manager.credentials_missing.connect(self._on_credentials_missing)
            self.setup_autocomplete()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.label = QLabel("🏷️ Tags")
        layout.addWidget(self.label)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter tags...")
        self.search_input.textChanged.connect(self._filter_tags)
        row.addWidget(self.search_input)

        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("Add tag...")
        self.add_input.returnPressed.connect(self._add_tag)
        row.addWidget(self.add_input)

        self.add_btn = QPushButton("➕")
        self.add_btn.clicked.connect(self._add_tag)
        row.addWidget(self.add_btn)

        layout.addLayout(row)

        self.tag_list = TagListWidget()
        self.tag_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.tag_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self._show_context_menu)
        self.tag_list.itemDoubleClicked.connect(self._on_item_double_click)
        self.tag_list.orderChanged.connect(self._on_order_changed)
        layout.addWidget(self.tag_list)

    def setup_autocomplete(self):
        self._autocomplete_popup = TagAutocompletePopup(self)
        self._autocomplete_popup.install_on(self.add_input)
        self._autocomplete_popup.tag_selected.connect(self._on_tag_selected)
        self.add_input.textChanged.connect(self._on_text_changed_for_autocomplete)
        self._last_api_query = ""

    def _on_tag_selected(self, tag):
        self.add_input.setText(tag)
        self._add_tag()

    def _on_text_changed_for_autocomplete(self, text):
        if len(text) < 1:
            self._autocomplete_popup.hide()
            self._last_api_query = ""
            return
        results = self.tag_db.search(text) if self.tag_db and self.tag_db.is_loaded else []
        # Compute anchor rect: directly below the input, same width
        global_pos = self.add_input.mapToGlobal(QPoint(0, self.add_input.height()))
        api_rect = QRect(global_pos, self.add_input.size())
        api_rect.setHeight(0)
        if results:
            self._autocomplete_popup.show_suggestions(
                [TagEntry(r['name'], r['category'], r['post_count'], source='db') for r in results],
                api_rect
            )
        else:
            self._autocomplete_popup.hide()
        if self.source_manager:
            self._last_api_query = text
            self.source_manager.autocomplete(text)

    def _on_autocomplete_results(self, query, tags):
        if not self.add_input.text().startswith(query):
            return
        if not tags:
            return
        db_results = self.tag_db.search(self.add_input.text()) if self.tag_db and self.tag_db.is_loaded else []
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
        global_pos = self.add_input.mapToGlobal(QPoint(0, self.add_input.height()))
        api_rect = QRect(global_pos, self.add_input.size())
        api_rect.setHeight(0)
        self._autocomplete_popup.show_suggestions(merged, api_rect)

    def _on_item_double_click(self, item):
        tag = item.text()
        if self.source_manager:
            self.show_tag_inspector(tag)

    def show_tag_inspector(self, tag):
        """Show the tag inspector as a separate popup window."""
        if not self.inspector:
            self.inspector = TagInspector()
        self.inspector.clear()
        self.inspector.show()
        self.inspector.raise_()
        self._current_inspected_tag = tag
        if self.source_manager:
            self.source_manager.fetch_tag_info(tag)
            self.source_manager.fetch_wiki(tag)
            self.source_manager.fetch_example_posts(tag)

    def _on_tag_info_fetched(self, tag, info):
        if tag != self._current_inspected_tag:
            return
        if self.inspector and self.inspector.isVisible():
            self.inspector.display_tag_info(tag, info)

    def _on_tag_info_error(self, tag, error):
        if tag != self._current_inspected_tag:
            return
        if self.inspector and self.inspector.isVisible():
            self.inspector.display_tag_info(tag, {"error": error})

    def _on_wiki_fetched(self, tag, body):
        if tag != self._current_inspected_tag:
            return
        if self.inspector and self.inspector.isVisible():
            self.inspector.display_wiki(tag, body)

    def _on_example_posts_fetched(self, tag, posts):
        if tag != self._current_inspected_tag:
            return
        if self.inspector and self.inspector.isVisible():
            self.inspector.display_example_posts(tag, posts)
            for i, post in enumerate(posts):
                url = post.get('preview_url')
                if url:
                    self.source_manager.fetch_preview_image(tag, i, url)

    def _on_preview_loaded(self, tag, index, pixmap):
        if tag != self._current_inspected_tag:
            return
        if self.inspector and self.inspector.isVisible():
            self.inspector.set_preview_image(tag, index, pixmap)

    def _on_credentials_missing(self):
        reply = QMessageBox.question(
            self, "Credentials Needed",
            "Danbooru API credentials are not set.\n"
            "Would you like to open settings now?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'open_settings'):
                    parent.open_settings()
                    break
                parent = parent.parent()

    def _on_tags_changed(self, new_tags):
        self.all_tags = new_tags
        self._apply_filter()

    def _apply_filter(self):
        filter_text = self.search_input.text().strip().lower()
        self.tag_list.clear()
        filtered = [t for t in self.all_tags if filter_text in t.lower()]
        for tag in filtered:
            self.tag_list.addItem(tag)
        self.tags_changed.emit(filtered)
        self.tag_list.setDragEnabled(not bool(filter_text))

    def _filter_tags(self, text):
        self.filter_text = text.strip().lower()
        self._apply_filter()

    def _add_tag(self):
        text = self.add_input.text().strip()
        if text:
            self.tag_manager.add_tag(text)
            self.add_input.clear()

    def _show_context_menu(self, pos):
        menu = QMenu()
        inspect_action = QAction("🔍 Inspect Tag", self)
        inspect_action.triggered.connect(self._inspect_selected)
        menu.addAction(inspect_action)
        delete_action = QAction("🗑️ Delete Selected", self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        delete_all_action = QAction("Delete All Tags", self)
        delete_all_action.triggered.connect(self._delete_all)
        menu.addAction(delete_all_action)
        menu.exec_(self.tag_list.mapToGlobal(pos))

    def _inspect_selected(self):
        items = self.tag_list.selectedItems()
        if items and self.source_manager:
            tag = items[0].text()
            self.show_tag_inspector(tag)

    def _delete_selected(self):
        items = self.tag_list.selectedItems()
        if items:
            tags_to_delete = [item.text() for item in items]
            self.tag_manager.remove_tags(tags_to_delete)

    def _delete_all(self):
        if self.all_tags:
            reply = QMessageBox.question(
                self, "Delete All",
                f"Delete all {len(self.all_tags)} tags?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.tag_manager.set_tags([])

    def _on_order_changed(self, new_order):
        self.tag_manager.reorder_tags(new_order)

    def get_selected_tags(self):
        return [item.text() for item in self.tag_list.selectedItems()]

    def clear(self):
        self.tag_list.clear()
        self.all_tags = []
        self.search_input.clear()
        self.add_input.clear()
        if self.inspector:
            self.inspector.close()
            self.inspector = None