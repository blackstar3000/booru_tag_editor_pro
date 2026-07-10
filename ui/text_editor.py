# ui/text_editor.py
"""
Quick Editor Pro – multi‑document text editor with syntax highlighting, file explorer, and Booru tools.
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QAction,
    QTabWidget, QTextEdit, QFileDialog, QMessageBox, QSplitter,
    QTreeView, QFileSystemModel, QMenu, QInputDialog, QPushButton,
    QLineEdit, QLabel, QDialog, QDialogButtonBox,
    QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QKeySequence, QFont, QTextCursor, QTextDocument

from core.syntax_highlighter import SyntaxHighlighter
from core.tag_highlighter import TagHighlighter
from core.danbooru_client import DanbooruClient
from core.danbooru_tag_db import DanbooruTagDB
from ui.tag_autocomplete import TagAutocompletePopup, TagEntry

import logging
logger = logging.getLogger(__name__)


class FindDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find")
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Search term...")
        row.addWidget(self.find_input)
        layout.addLayout(row)

        self.case_check = QCheckBox("Case Sensitive")
        layout.addWidget(self.case_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_search_params(self):
        return self.find_input.text(), self.case_check.isChecked()


class EditorTab(QTextEdit):
    def __init__(self, file_path=None, danbooru_client=None, tag_db: DanbooruTagDB = None):
        super().__init__()
        self.file_path = file_path
        self.danbooru_client = danbooru_client
        self.tag_db = tag_db
        self.syntax_highlighter = None
        self.tag_highlighter = None
        self.modified = False
        self.document().modificationChanged.connect(self._on_modification_changed)
        self.tag_cache = {}  # tag -> category
        self._autocomplete_connected = False  # tracks this tab's own connection to the shared signal
        self._warned_missing_credentials = False
        self._autocomplete_popup = None

        font = QFont("Courier New", 10)
        self.setFont(font)

        if file_path and file_path.exists():
            self.load_file(file_path)

        # Autocomplete for .txt files
        if self.file_path and self.file_path.suffix.lower() == ".txt":
            self.setup_autocomplete()

        self.setAcceptRichText(False)
        self.setTabStopWidth(4)

    def load_file(self, path):
        self.file_path = path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.setPlainText(content)
            self.document().setModified(False)
            self.modified = False
            self._apply_highlighter()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load file:\n{e}")

    def save_file(self):
        if not self.file_path:
            return False
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.toPlainText())
            self.document().setModified(False)
            self.modified = False
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")
            return False

    def save_file_as(self, new_path):
        self.file_path = new_path
        return self.save_file()

    def _on_modification_changed(self, modified):
        self.modified = modified

    def _apply_highlighter(self):
        if not self.file_path:
            return
        suffix = self.file_path.suffix.lower()
        self.syntax_highlighter = None
        self.tag_highlighter = None
        if suffix in ('.py', '.js', '.html', '.css', '.json', '.yaml', '.md'):
            file_type = suffix[1:]
            self.syntax_highlighter = SyntaxHighlighter(self.document(), file_type)
        elif suffix == '.txt':
            if self.danbooru_client:
                self.tag_highlighter = TagHighlighter(self.document(), self._get_tag_category)

    def _get_tag_category(self, tag):
        if tag in self.tag_cache:
            return self.tag_cache[tag]
        self.tag_cache[tag] = 0
        return 0

    def setup_autocomplete(self):
        self._autocomplete_popup = TagAutocompletePopup(self)
        self._autocomplete_popup.tag_selected.connect(self._insert_suggestion)
        self.textChanged.connect(self._on_text_changed_for_autocomplete)

    def _on_text_changed_for_autocomplete(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()
        if len(word) >= 1:
            db_results = self.tag_db.search(word) if self.tag_db and self.tag_db.is_loaded else []
            if db_results:
                entries = [TagEntry(r['name'], r['category'], r['post_count'], source='db') for r in db_results]
                rect = self.cursorRect(cursor)
                anchor = QRect(self.mapToGlobal(rect.bottomLeft()), rect.size())
                self._autocomplete_popup.show_suggestions(entries, anchor)
            if self.danbooru_client:
                if not self._autocomplete_connected:
                    self.danbooru_client.autocomplete_results.connect(self._on_autocomplete_results)
                    self.danbooru_client.credentials_missing.connect(self._on_credentials_missing)
                    self._autocomplete_connected = True
                self.danbooru_client.autocomplete(word)
        else:
            self._autocomplete_popup.hide()

    def disconnect_autocomplete(self):
        """Detach this tab from the shared autocomplete signal. Call before
        the tab is closed/discarded so it stops receiving results it no
        longer needs."""
        if self._autocomplete_connected and self.danbooru_client:
            try:
                self.danbooru_client.autocomplete_results.disconnect(self._on_autocomplete_results)
            except TypeError:
                pass
            try:
                self.danbooru_client.credentials_missing.disconnect(self._on_credentials_missing)
            except TypeError:
                pass
            self._autocomplete_connected = False

    def _on_credentials_missing(self):
        """DanbooruClient.autocomplete() emits this instead of
        autocomplete_results when no Danbooru username/API key is
        configured - without this handler the editor just silently never
        shows suggestions. Warn once per tab instead of failing silently
        (and without popping a dialog on every keystroke)."""
        if self._warned_missing_credentials:
            return
        self._warned_missing_credentials = True
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                "Tag autocomplete needs Danbooru credentials - set them in Settings.", 8000
            )

    def _on_autocomplete_results(self, query, tags):
        if not tags:
            self._autocomplete_popup.hide()
            return
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()
        if word != query:
            self._autocomplete_popup.hide()
            return

        db_results = self.tag_db.search(word) if self.tag_db and self.tag_db.is_loaded else []
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
        rect = self.cursorRect(cursor)
        anchor = QRect(self.mapToGlobal(rect.bottomLeft()), rect.size())
        self._autocomplete_popup.show_suggestions(merged, anchor)

    def _insert_suggestion(self, tag):
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(tag)
        self._autocomplete_popup.hide()

    def keyPressEvent(self, event):
        if self._autocomplete_popup and self._autocomplete_popup.isVisible():
            if self._autocomplete_popup._handle_key(event):
                return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self._autocomplete_popup:
            self._autocomplete_popup.hide()
        super().focusOutEvent(event)


class TextEditor(QMainWindow):
    def __init__(self, danbooru_client=None, tag_db: DanbooruTagDB = None, parent=None):
        super().__init__(parent)
        self.danbooru_client = danbooru_client
        self.tag_db = tag_db
        self.setWindowTitle("📝 Quick Editor Pro")
        self.setGeometry(100, 100, 1200, 800)
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._connect_signals()
        self._load_recent_files()

    def _create_menu_bar(self):
        menubar = self.menuBar()
        # File menu
        file_menu = menubar.addMenu("File")
        new_action = QAction("New", self)
        new_action.triggered.connect(self._new_file)
        new_action.setShortcut(QKeySequence.New)
        file_menu.addAction(new_action)
        open_action = QAction("Open...", self)
        open_action.triggered.connect(self._open_file)
        open_action.setShortcut(QKeySequence.Open)
        file_menu.addAction(open_action)
        open_folder_action = QAction("Open Folder...", self)
        open_folder_action.triggered.connect(self._open_folder)
        open_folder_action.setShortcut(QKeySequence("Ctrl+K Ctrl+O"))
        file_menu.addAction(open_folder_action)
        file_menu.addSeparator()
        save_action = QAction("Save", self)
        save_action.triggered.connect(self._save_file)
        save_action.setShortcut(QKeySequence.Save)
        file_menu.addAction(save_action)
        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self._save_file_as)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        file_menu.addAction(save_as_action)
        save_all_action = QAction("Save All", self)
        save_all_action.triggered.connect(self._save_all)
        save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(save_all_action)
        file_menu.addSeparator()
        close_tab_action = QAction("Close Tab", self)
        close_tab_action.triggered.connect(self._close_current_tab)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        file_menu.addAction(close_tab_action)
        close_window_action = QAction("Close Window", self)
        close_window_action.triggered.connect(self.close)
        close_window_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        file_menu.addAction(close_window_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut(QKeySequence.Quit)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self._undo)
        undo_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self._redo)
        redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        cut_action = QAction("Cut", self)
        cut_action.triggered.connect(self._cut)
        cut_action.setShortcut(QKeySequence.Cut)
        edit_menu.addAction(cut_action)
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy)
        copy_action.setShortcut(QKeySequence.Copy)
        edit_menu.addAction(copy_action)
        paste_action = QAction("Paste", self)
        paste_action.triggered.connect(self._paste)
        paste_action.setShortcut(QKeySequence.Paste)
        edit_menu.addAction(paste_action)
        edit_menu.addSeparator()
        find_action = QAction("Find", self)
        find_action.triggered.connect(self._find)
        find_action.setShortcut(QKeySequence.Find)
        edit_menu.addAction(find_action)
        replace_action = QAction("Replace", self)
        replace_action.triggered.connect(self._replace)
        replace_action.setShortcut(QKeySequence.Replace)
        edit_menu.addAction(replace_action)

    def _create_toolbar(self):
        toolbar = self.addToolBar("Editor")
        toolbar.setMovable(False)
        # New
        new_action = QAction("📄 New", self)
        new_action.triggered.connect(self._new_file)
        toolbar.addAction(new_action)
        # Open
        open_action = QAction("📂 Open", self)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)
        # Save
        save_action = QAction("💾 Save", self)
        save_action.triggered.connect(self._save_file)
        toolbar.addAction(save_action)
        # Save All
        save_all_action = QAction("💾💾 Save All", self)
        save_all_action.triggered.connect(self._save_all)
        toolbar.addAction(save_all_action)
        toolbar.addSeparator()
        # Undo/Redo
        undo_action = QAction("↩ Undo", self)
        undo_action.triggered.connect(self._undo)
        undo_action.setShortcut(QKeySequence.Undo)
        toolbar.addAction(undo_action)
        redo_action = QAction("↪ Redo", self)
        redo_action.triggered.connect(self._redo)
        redo_action.setShortcut(QKeySequence.Redo)
        toolbar.addAction(redo_action)
        toolbar.addSeparator()
        # Cut/Copy/Paste
        cut_action = QAction("✂️ Cut", self)
        cut_action.triggered.connect(self._cut)
        toolbar.addAction(cut_action)
        copy_action = QAction("📋 Copy", self)
        copy_action.triggered.connect(self._copy)
        toolbar.addAction(copy_action)
        paste_action = QAction("📋 Paste", self)
        paste_action.triggered.connect(self._paste)
        toolbar.addAction(paste_action)
        toolbar.addSeparator()
        # Find/Replace
        find_action = QAction("🔍 Find", self)
        find_action.triggered.connect(self._find)
        toolbar.addAction(find_action)
        replace_action = QAction("🔄 Replace", self)
        replace_action.triggered.connect(self._replace)
        toolbar.addAction(replace_action)
        toolbar.addSeparator()
        # Word wrap toggle
        self.word_wrap_action = QAction("📏 Wrap", self)
        self.word_wrap_action.setCheckable(True)
        self.word_wrap_action.setChecked(False)
        self.word_wrap_action.triggered.connect(self._toggle_word_wrap)
        toolbar.addAction(self.word_wrap_action)
        # Zoom
        zoom_in_action = QAction("🔍+ Zoom In", self)
        zoom_in_action.triggered.connect(self._zoom_in)
        toolbar.addAction(zoom_in_action)
        zoom_out_action = QAction("🔍- Zoom Out", self)
        zoom_out_action.triggered.connect(self._zoom_out)
        toolbar.addAction(zoom_out_action)
        reset_zoom_action = QAction("🔍 Reset Zoom", self)
        reset_zoom_action.triggered.connect(self._reset_zoom)
        toolbar.addAction(reset_zoom_action)

    def _create_central_widget(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QHBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Splitter: file explorer + tab widget
        splitter = QSplitter(Qt.Horizontal)

        # File explorer
        self.explorer = QTreeView()
        self.explorer.setMinimumWidth(220)
        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.explorer.setModel(self.model)
        for col in range(1, self.model.columnCount()):
            self.explorer.hideColumn(col)
        self.explorer.clicked.connect(self._on_explorer_clicked)
        self.explorer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.explorer.customContextMenuRequested.connect(self._explorer_context_menu)
        splitter.addWidget(self.explorer)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        splitter.addWidget(self.tab_widget)

        splitter.setSizes([280, 800])
        layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _connect_signals(self):
        # Save shortcuts
        pass

    def _load_recent_files(self):
        # Placeholder – we can load from settings later
        pass

    # --- Actions ---
    def _new_file(self):
        tab = EditorTab(danbooru_client=self.danbooru_client, tag_db=self.tag_db)
        idx = self.tab_widget.addTab(tab, "Untitled*")
        self.tab_widget.setCurrentIndex(idx)

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Text Files (*.txt);;JSON (*.json);;YAML (*.yaml);;Markdown (*.md);;Python (*.py);;JavaScript (*.js);;HTML (*.html);;CSS (*.css)")
        if file_path:
            self._open_file_path(Path(file_path))

    def _open_file_path(self, path):
        # Check if already open
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if tab.file_path == path:
                self.tab_widget.setCurrentIndex(i)
                return
        tab = EditorTab(path, danbooru_client=self.danbooru_client, tag_db=self.tag_db)
        idx = self.tab_widget.addTab(tab, path.name)
        self.tab_widget.setCurrentIndex(idx)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.explorer.setRootIndex(self.model.setRootPath(folder))

    def _save_file(self):
        tab = self._current_tab()
        if not tab:
            return
        if not tab.file_path:
            # New/untitled tab has nowhere to save yet - fall back to Save As
            # instead of silently doing nothing.
            self._save_file_as()
            return
        if tab.save_file():
            self.statusBar().showMessage(f"Saved {tab.file_path.name}")
            self._update_tab_title(tab)

    def _save_file_as(self):
        tab = self._current_tab()
        if tab:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "All Files (*);;Text Files (*.txt);;JSON (*.json);;YAML (*.yaml);;Markdown (*.md);;Python (*.py);;JavaScript (*.js);;HTML (*.html);;CSS (*.css)")
            if file_path:
                if tab.save_file_as(Path(file_path)):
                    self.statusBar().showMessage(f"Saved as {Path(file_path).name}")
                    self._update_tab_title(tab)
                    self._update_tab_tooltip(tab)

    def _save_all(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if tab.modified:
                tab.save_file()
        self.statusBar().showMessage("All files saved")

    def _undo(self):
        tab = self._current_tab()
        if tab:
            tab.undo()

    def _redo(self):
        tab = self._current_tab()
        if tab:
            tab.redo()

    def _cut(self):
        tab = self._current_tab()
        if tab:
            tab.cut()

    def _copy(self):
        tab = self._current_tab()
        if tab:
            tab.copy()

    def _paste(self):
        tab = self._current_tab()
        if tab:
            tab.paste()

    def _find(self):
        tab = self._current_tab()
        if not tab:
            return
        dlg = FindDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            search_text, case_sensitive = dlg.get_search_params()
            if not search_text:
                return
            cursor = tab.textCursor()
            flags = QTextDocument.FindFlags()
            if case_sensitive:
                flags |= QTextDocument.FindCaseSensitively
            cursor = tab.document().find(search_text, cursor, flags)
            if not cursor.isNull():
                tab.setTextCursor(cursor)
            else:
                QMessageBox.information(self, "Find", "No more matches found.")

    def _replace(self):
        tab = self._current_tab()
        if not tab:
            return
        find_text, ok = QInputDialog.getText(self, "Replace", "Find:")
        if not ok or not find_text:
            return
        replace_text, ok = QInputDialog.getText(self, "Replace", "Replace with:")
        if not ok:
            return
        text = tab.toPlainText()
        if not text:
            return
        new_text = text.replace(find_text, replace_text)
        if new_text != text:
            tab.setPlainText(new_text)
            self.statusBar().showMessage(f"Replaced all occurrences.")

    def _toggle_word_wrap(self):
        tab = self._current_tab()
        if tab:
            if self.word_wrap_action.isChecked():
                tab.setLineWrapMode(QTextEdit.WidgetWidth)
            else:
                tab.setLineWrapMode(QTextEdit.NoWrap)

    def _zoom_in(self):
        tab = self._current_tab()
        if tab:
            font = tab.font()
            font.setPointSize(font.pointSize() + 1)
            tab.setFont(font)

    def _zoom_out(self):
        tab = self._current_tab()
        if tab:
            font = tab.font()
            font.setPointSize(max(6, font.pointSize() - 1))
            tab.setFont(font)

    def _reset_zoom(self):
        tab = self._current_tab()
        if tab:
            font = QFont("Courier New", 10)
            tab.setFont(font)

    def _current_tab(self):
        return self.tab_widget.currentWidget()

    def _on_tab_changed(self, index):
        tab = self.tab_widget.widget(index)
        if tab:
            self._update_tab_title(tab)
            self._update_tab_tooltip(tab)

    def _update_tab_title(self, tab):
        idx = self.tab_widget.indexOf(tab)
        if idx >= 0:
            name = tab.file_path.name if tab.file_path else "Untitled"
            if tab.modified:
                name += "●"
            self.tab_widget.setTabText(idx, name)

    def _update_tab_tooltip(self, tab):
        idx = self.tab_widget.indexOf(tab)
        if idx >= 0 and tab.file_path:
            self.tab_widget.setTabToolTip(idx, str(tab.file_path))

    def _on_explorer_clicked(self, index):
        path = self.model.filePath(index)
        if Path(path).is_file():
            self._open_file_path(Path(path))

    def _explorer_context_menu(self, point):
        menu = QMenu()
        new_file_action = QAction("New File", self)
        new_file_action.triggered.connect(self._explorer_new_file)
        menu.addAction(new_file_action)
        new_folder_action = QAction("New Folder", self)
        new_folder_action.triggered.connect(self._explorer_new_folder)
        menu.addAction(new_folder_action)
        menu.addSeparator()
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._explorer_rename)
        menu.addAction(rename_action)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._explorer_delete)
        menu.addAction(delete_action)
        menu.exec_(self.explorer.mapToGlobal(point))

    def _explorer_new_file(self):
        index = self.explorer.currentIndex()
        if not index.isValid():
            return
        path = Path(self.model.filePath(index))
        if path.is_file():
            path = path.parent
        name, ok = QInputDialog.getText(self, "New File", "Enter file name:")
        if ok and name:
            new_path = path / name
            if not new_path.exists():
                new_path.touch()
                self.explorer.setRootIndex(self.model.setRootPath(str(path.parent)))
                self._open_file_path(new_path)

    def _explorer_new_folder(self):
        index = self.explorer.currentIndex()
        if not index.isValid():
            return
        path = Path(self.model.filePath(index))
        if path.is_file():
            path = path.parent
        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name:
            new_path = path / name
            if not new_path.exists():
                new_path.mkdir()

    def _explorer_rename(self):
        index = self.explorer.currentIndex()
        if not index.isValid():
            return
        path = Path(self.model.filePath(index))
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=path.name)
        if ok and name:
            new_path = path.parent / name
            if not new_path.exists():
                path.rename(new_path)
                # If this file is open in a tab, point it at the new path too -
                # otherwise the tab keeps writing to the old (now-gone) location.
                for i in range(self.tab_widget.count()):
                    tab = self.tab_widget.widget(i)
                    if tab.file_path == path:
                        tab.file_path = new_path
                        self._update_tab_title(tab)
                        self._update_tab_tooltip(tab)
                        break

    def _explorer_delete(self):
        index = self.explorer.currentIndex()
        if not index.isValid():
            return
        path = Path(self.model.filePath(index))
        if QMessageBox.question(self, "Delete", f"Delete {path.name}?") == QMessageBox.Yes:
            if path.is_file():
                path.unlink()
            else:
                import shutil
                shutil.rmtree(path)

    def _close_tab(self, index):
        tab = self.tab_widget.widget(index)
        if tab.modified:
            reply = QMessageBox.question(self, "Unsaved Changes", f"Save changes to {tab.file_path.name if tab.file_path else 'Untitled'}?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            elif reply == QMessageBox.Save:
                if not tab.file_path:
                    # Untitled tab - prompt for a save location instead of
                    # silently failing to save.
                    file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "All Files (*);;Text Files (*.txt);;JSON (*.json);;YAML (*.yaml);;Markdown (*.md);;Python (*.py);;JavaScript (*.js);;HTML (*.html);;CSS (*.css)")
                    if not file_path or not tab.save_file_as(Path(file_path)):
                        return
                elif not tab.save_file():
                    return
        tab.disconnect_autocomplete()
        self.tab_widget.removeTab(index)

    def _close_current_tab(self):
        if self.tab_widget.count() > 0:
            self._close_tab(self.tab_widget.currentIndex())

    def closeEvent(self, event):
        # Check all tabs
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if tab.modified:
                reply = QMessageBox.question(self, "Unsaved Changes", f"Save changes to {tab.file_path.name if tab.file_path else 'Untitled'}?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.Save:
                    if not tab.file_path:
                        file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "All Files (*);;Text Files (*.txt);;JSON (*.json);;YAML (*.yaml);;Markdown (*.md);;Python (*.py);;JavaScript (*.js);;HTML (*.html);;CSS (*.css)")
                        if not file_path or not tab.save_file_as(Path(file_path)):
                            event.ignore()
                            return
                    elif not tab.save_file():
                        event.ignore()
                        return
        event.accept()