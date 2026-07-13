import json
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QAction,
    QSplitter, QTabWidget, QStatusBar, QMessageBox, QFileDialog, QApplication,
    QLabel, QTextEdit, QPushButton, QCheckBox, QComboBox, QMenu
)
from PyQt5.QtCore import Qt, QThreadPool, QEvent
from PyQt5.QtGui import QIcon, QKeySequence, QGuiApplication, QCursor

from core.image_loader import ImageLoader
from core.metadata_reader import MetadataReader
from core.settings_manager import SettingsManager
from core.tag_manager import TagManager
from core.danbooru_tag_db import DanbooruTagDB
from core.navigation_controller import NavigationController
from core.booru_source_manager import BooruSourceManager
from workers.folder_scan_worker import FolderScanWorker
from workers.metadata_worker import MetadataWorker
from ui.image_viewer import ImageViewer
from ui.tag_panel import TagPanel
from ui.metadata_panel import MetadataPanel
from ui.folder_tree import FolderTree
from ui.filmstrip import Filmstrip
from ui.prompt_builder import PromptBuilder
from ui.statistics_dashboard import StatisticsDashboard
from ui.duplicate_finder import DuplicateFinder
from ui.dataset_audit import DatasetAudit
from ui.smart_tools import SmartTools
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.batch_dialog import BatchDialog
from ui.dialogs.workspace_save_dialog import SaveWorkspaceDialog
from ui.dialogs.workspace_manager_dialog import WorkspaceManagerDialog
from ui.dialogs.source_manager_dialog import SourceManagerDialog
from ui.dialogs.fetch_post_dialog import FetchPostDialog
from ui.dialogs.booru_search_dialog import BooruSearchDialog
from ui.dialogs.tag_validator_dialog import TagValidatorDialog
from core.workspace_manager import WorkspaceManager
from ui.text_editor import TextEditor
from ui.tooltips import attach_tooltip, register_tooltips
from ui.windows_theme import dark_get_text, dark_question, dark_information, dark_warning, dark_critical

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager, source_manager: BooruSourceManager):
        super().__init__()
        self.settings = settings
        self.source_manager = source_manager
        self.setWindowTitle("🧊 Booru Tag Editor Pro++")
        self.text_editor = None  # keep reference

        self.tag_db = DanbooruTagDB()
        self.tag_db.load()

        self.threadpool = QThreadPool()
        logger.info(f"Thread pool max threads: {self.threadpool.maxThreadCount()}")

        self.image_loader = ImageLoader(cache_size=500)
        self.metadata_reader = MetadataReader()
        self.tag_manager = TagManager()
        self.nav = NavigationController()

        self.metadata_cache = {}   # path -> metadata dict
        self.current_ai_metadata = None
        self.show_raw_metadata = False
        self.current_folder = None

        self.workspace_manager = WorkspaceManager()
        self.current_workspace_name = ""

        self.setup_ui()
        self.update_status()
        self.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)

        # Connect navigation signals
        self.nav.folder_loaded.connect(self._on_folder_loaded)
        self.nav.image_list_changed.connect(self._on_image_list_changed)
        self.nav.current_image_changed.connect(self._on_current_image_changed)
        self.nav.sort_order_changed.connect(self._on_sort_order_changed)

        # Connect tag manager signals
        self.tag_manager.tags_changed.connect(self._on_tags_changed)
        self.tag_manager.dirty_changed.connect(self.update_status)

        # Auto-load last folder
        folders = self.settings.recent_folders
        if folders:
            last = folders[0]
            if Path(last).exists():
                self.folder_tree.set_root_path(last)
                self.nav.load_folder(last)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # File menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_folder_action = QAction("📂 Open Folder...", self)
        open_folder_action.triggered.connect(self.open_folder)
        open_folder_action.setShortcut(QKeySequence("Ctrl+O"))
        file_menu.addAction(open_folder_action)

        self.recent_menu = file_menu.addMenu("📁 Recent Folders")
        self.recent_menu.aboutToShow.connect(self._populate_recent_menu)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Toolbar
        self.main_toolbar = self.addToolBar("Main")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setObjectName("MainToolbar")
        toolbar = self.main_toolbar

        self.open_action = QAction("Open Folder", self)
        self.open_action.triggered.connect(self.open_folder)
        toolbar.addAction(self.open_action)

        up_action = QAction("Up", self)
        up_action.triggered.connect(self._go_up)
        up_action.setShortcut(QKeySequence("Ctrl+U"))
        toolbar.addAction(up_action)
        self.up_action = up_action

        toolbar.addSeparator()

        self.prev_action = QAction("Prev", self)
        self.prev_action.triggered.connect(lambda: self.nav.navigate(-1))
        self.prev_action.setShortcut(QKeySequence(Qt.Key_Left))
        toolbar.addAction(self.prev_action)

        self.next_action = QAction("Next", self)
        self.next_action.triggered.connect(lambda: self.nav.navigate(1))
        self.next_action.setShortcut(QKeySequence(Qt.Key_Right))
        toolbar.addAction(self.next_action)

        # Sorting dropdown
        toolbar.addSeparator()
        sort_label = QLabel("Sort:")
        toolbar.addWidget(sort_label)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["name", "date", "size", "random"])
        self.sort_combo.setCurrentText(self.nav.sort_order)
        self.sort_combo.currentTextChanged.connect(self.nav.set_sort_order)
        toolbar.addWidget(self.sort_combo)

        toolbar.addSeparator()

        # Save, Undo, Redo
        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.save_current_tags)
        self.save_action.setShortcut(QKeySequence.Save)
        toolbar.addAction(self.save_action)

        self.undo_action = QAction("Undo", self)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setShortcut(QKeySequence.Undo)
        toolbar.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setShortcut(QKeySequence.Redo)
        toolbar.addAction(self.redo_action)

        toolbar.addSeparator()

        # Batch button
        self.batch_action = QAction("Batch", self)
        self.batch_action.triggered.connect(self.open_batch_dialog)
        toolbar.addAction(self.batch_action)

        toolbar.addSeparator()

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)

        # Add Text Editor button
        self.text_editor_action = QAction("Text Editor", self)
        self.text_editor_action.triggered.connect(self.open_text_editor)
        toolbar.addAction(self.text_editor_action)

        toolbar.addSeparator()

        # Sources button
        self.sources_btn = QPushButton("Sources  ▾")
        self.sources_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(59, 130, 246, 0.2); "
            "border: 1px solid rgba(59, 130, 246, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(59, 130, 246, 0.35); color: #fff; }"
        )
        self.sources_btn.clicked.connect(self._open_source_manager)
        toolbar.addWidget(self.sources_btn)

        # Fetch Post button
        self.fetch_post_btn = QPushButton("🔗 Fetch Tags")
        self.fetch_post_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(16, 185, 129, 0.2); "
            "border: 1px solid rgba(16, 185, 129, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(16, 185, 129, 0.35); color: #fff; }"
        )
        self.fetch_post_btn.clicked.connect(self._open_fetch_post)
        toolbar.addWidget(self.fetch_post_btn)

        # Booru Search button
        self.booru_search_btn = QPushButton("🔎 Booru Search")
        self.booru_search_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(99, 102, 241, 0.2); "
            "border: 1px solid rgba(99, 102, 241, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(99, 102, 241, 0.35); color: #fff; }"
        )
        self.booru_search_btn.clicked.connect(self._open_booru_search)
        toolbar.addWidget(self.booru_search_btn)

        # Tag Validator button
        self.tag_validator_btn = QPushButton("✅ Tag Validator")
        self.tag_validator_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(16, 185, 129, 0.2); "
            "border: 1px solid rgba(16, 185, 129, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(16, 185, 129, 0.35); color: #fff; }"
        )
        self.tag_validator_btn.clicked.connect(self._open_tag_validator)
        toolbar.addWidget(self.tag_validator_btn)

        # LLM Tag Generator button
        self.llm_generator_btn = QPushButton("🧠 LLM Generator")
        self.llm_generator_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(236, 72, 153, 0.2); "
            "border: 1px solid rgba(236, 72, 153, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(236, 72, 153, 0.35); color: #fff; }"
        )
        self.llm_generator_btn.clicked.connect(self._open_llm_generator)
        toolbar.addWidget(self.llm_generator_btn)

        # Workspaces button
        self.workspace_menu_btn = QPushButton("Workspaces  ▾")
        self.workspace_menu_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 12px; "
            "background: rgba(139, 92, 246, 0.2); "
            "border: 1px solid rgba(139, 92, 246, 0.3); "
            "border-radius: 8px; color: #ccc; font-weight: bold; }"
            "QPushButton:hover { background: rgba(139, 92, 246, 0.35); color: #fff; }"
        )
        self.workspace_menu_btn.clicked.connect(self._show_workspace_menu)
        toolbar.addWidget(self.workspace_menu_btn)

        # Main splitter: left side (image viewer + folder tree) | right side (tabs)
        self.main_splitter = QSplitter(Qt.Horizontal)
        # Don't let either side collapse to 0 width when dragged too far -
        # that's what makes the handle feel like it "went off screen".
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStyleSheet("QSplitter { background: transparent; }")

        # Left side: vertical splitter with image viewer and folder tree
        left_container = QWidget()
        left_container.setObjectName("glassPanel")
        left_container.setStyleSheet(
            "#glassPanel { background: rgba(16, 18, 26, 0.55); "
            "border: 1px solid rgba(255, 255, 255, 0.05); "
            "border-radius: 12px; }"
        )
        left_container.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setStyleSheet("QSplitter { background: transparent; }")
        # Left collapsible on purpose: this lets you pull the folder tree
        # all the way down to give the image full height, same as before.
        self.image_viewer = ImageViewer()
        self.image_viewer.context_menu_requested.connect(self._show_image_context_menu)
        self.left_splitter.addWidget(self.image_viewer)

        self.folder_tree = FolderTree()
        self.folder_tree.file_selected.connect(self._on_file_selected_from_tree)
        self.folder_tree.folder_selected.connect(self._on_folder_selected_from_tree)
        self.left_splitter.addWidget(self.folder_tree)
        self.left_splitter.setSizes([500, 200])

        left_layout.addWidget(self.left_splitter)
        self.main_splitter.addWidget(left_container)

        # Right side: tabs
        right_container = QWidget()
        right_container.setObjectName("glassPanel")
        right_container.setStyleSheet(
            "#glassPanel { background: rgba(16, 18, 26, 0.55); "
            "border: 1px solid rgba(255, 255, 255, 0.05); "
            "border-radius: 12px; }"
        )
        right_container.setMinimumWidth(300)
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(4, 4, 4, 4)

        self.right_panel = QTabWidget()

        # Tags tab
        self.tag_panel = TagPanel(self.tag_manager, self.source_manager, tag_db=self.tag_db)
        self.right_panel.addTab(self.tag_panel, "🏷️ Tags")

        # EXIF Metadata tab
        self.metadata_panel = MetadataPanel()
        self.right_panel.addTab(self.metadata_panel, "📋 Metadata")

        # AI Metadata tab
        ai_metadata_widget = QWidget()
        ai_layout = QVBoxLayout(ai_metadata_widget)
        ai_layout.setContentsMargins(0, 0, 0, 0)

        button_row = QHBoxLayout()
        self.copy_prompt_btn = QPushButton("📋 Copy Prompt")
        self.copy_prompt_btn.clicked.connect(self.copy_prompt_to_clipboard)
        self.copy_prompt_btn.setEnabled(False)
        button_row.addWidget(self.copy_prompt_btn)

        self.import_tags_btn = QPushButton("🏷️ Import Tags")
        self.import_tags_btn.clicked.connect(self.import_tags_from_prompt)
        self.import_tags_btn.setEnabled(False)
        button_row.addWidget(self.import_tags_btn)

        self.raw_toggle = QCheckBox("Show Raw Metadata")
        self.raw_toggle.setChecked(False)
        self.raw_toggle.toggled.connect(self._on_raw_toggle)
        button_row.addWidget(self.raw_toggle)

        button_row.addStretch()
        ai_layout.addLayout(button_row)

        self.ai_metadata_panel = QTextEdit()
        self.ai_metadata_panel.setReadOnly(True)
        self.ai_metadata_panel.setPlaceholderText("No AI metadata found.")
        ai_layout.addWidget(self.ai_metadata_panel)

        self.right_panel.addTab(ai_metadata_widget, "🧠 AI Metadata")

        # Prompt Builder tab
        self.prompt_builder = PromptBuilder(self.source_manager, tag_db=self.tag_db)
        self.prompt_builder.prompt_changed.connect(self._on_prompt_builder_apply)
        self.prompt_builder.seed_requested.connect(self._on_seed_requested)
        self.prompt_builder.grouping_completed.connect(self._on_grouping_completed)
        self.right_panel.addTab(self.prompt_builder, "📝 Prompt Builder")

        # Statistics Dashboard tab
        self.stats_dashboard = StatisticsDashboard()
        self.right_panel.addTab(self.stats_dashboard, "📊 Statistics")

        # Duplicate Finder tab
        self.duplicate_finder = DuplicateFinder()
        self.right_panel.addTab(self.duplicate_finder, "🔍 Duplicates")

        # Dataset Audit tab
        self.dataset_audit = DatasetAudit()
        self.right_panel.addTab(self.dataset_audit, "📋 Dataset Audit")

        # Smart Tools tab
        self.smart_tools = SmartTools()
        self.smart_tools.filter_applied.connect(self._on_smart_collection_applied)
        self.right_panel.addTab(self.smart_tools, "🧠 Smart Tools")

        right_container_layout.addWidget(self.right_panel)
        self.main_splitter.addWidget(right_container)
        self.main_splitter.setSizes([600, 400])
        layout.addWidget(self.main_splitter)

        # Filmstrip
        filmstrip_container = QWidget()
        filmstrip_container.setObjectName("glassPanel")
        filmstrip_container.setStyleSheet(
            "#glassPanel { background: rgba(16, 18, 26, 0.55); "
            "border: 1px solid rgba(255, 255, 255, 0.05); "
            "border-radius: 12px; }"
        )
        filmstrip_layout = QVBoxLayout(filmstrip_container)
        filmstrip_layout.setContentsMargins(4, 4, 4, 4)

        self.filmstrip = Filmstrip(self.image_loader)
        self.filmstrip.image_selected.connect(self._on_filmstrip_selected)
        self.filmstrip.setMinimumHeight(100)
        filmstrip_layout.addWidget(self.filmstrip)
        layout.addWidget(filmstrip_container)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            "QStatusBar { background: rgba(13, 15, 20, 0.7); "
            "color: #777; border-top: 1px solid rgba(255, 255, 255, 0.04); "
            "font-size: 12px; padding: 3px 10px; }"
        )
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #888; padding: 2px;")
        self.status_bar.addWidget(self.status_label)

        self.update_status()
        self._update_up_button_state()

        # ── Attach glassmorphism tooltips ────────────────────────
        self._register_tooltips()

    def _populate_recent_menu(self):
        self.recent_menu.clear()
        folders = self.settings.recent_folders
        if not folders:
            empty = self.recent_menu.addAction("(no recent folders)")
            empty.setEnabled(False)
            return
        for folder in folders:
            name = Path(folder).name or folder
            act = self.recent_menu.addAction(f"{name}  ({folder})")
            act.setData(folder)
        self.recent_menu.addSeparator()
        clear_act = self.recent_menu.addAction("Clear Recent Folders")
        clear_act.triggered.connect(self._clear_recent_folders)
        self.recent_menu.triggered.connect(self._on_recent_folder_clicked)

    def _on_recent_folder_clicked(self, action):
        folder = action.data()
        if folder:
            self.folder_tree.set_root_path(folder)
            self.nav.load_folder(folder)

    def _clear_recent_folders(self):
        self.settings.recent_folders = []

    def _update_up_button_state(self):
        """Enable/disable the Up button based on whether we can go up."""
        if not self.nav.current_folder:
            self.up_action.setEnabled(False)
            return
        parent = Path(self.nav.current_folder).parent
        # If the parent is the same as the current, we're at the root (e.g., drive root on Windows)
        self.up_action.setEnabled(str(parent) != self.nav.current_folder)

    def _register_tooltips(self):
        """Register glassmorphism tooltips for all toolbar buttons."""
        # Configs keyed by QAction (or the workspace button which is a QPushButton)
        configs_by_action = {
            self.open_action: {
                "title": "Open Folder",
                "description": "Choose a folder containing images to begin editing.",
                "icon": "📂",
                "shortcut": "Ctrl + O",
            },
            self.up_action: {
                "title": "Up",
                "description": "Navigate to the parent folder.",
                "icon": "⬆️",
                "shortcut": "Ctrl + U",
            },
            self.prev_action: {
                "title": "Previous",
                "description": "Move to the previous image.",
                "icon": "◀️",
                "shortcut": "Left",
            },
            self.next_action: {
                "title": "Next",
                "description": "Move to the next image.",
                "icon": "▶️",
                "shortcut": "Right",
            },
            self.save_action: {
                "title": "Save",
                "description": "Save all edits made to the current image.",
                "icon": "💾",
                "shortcut": "Ctrl + S",
            },
            self.undo_action: {
                "title": "Undo",
                "description": "Undo the last action.",
                "icon": "↩️",
                "shortcut": "Ctrl + Z",
            },
            self.redo_action: {
                "title": "Redo",
                "description": "Redo the previously undone action.",
                "icon": "↪️",
                "shortcut": "Ctrl + Y",
            },
            self.batch_action: {
                "title": "Batch",
                "description": "Perform actions on multiple images at once.",
                "icon": "📦",
            },
            self.settings_action: {
                "title": "Settings",
                "description": "Configure application preferences and behavior.",
                "icon": "⚙️",
            },
            self.text_editor_action: {
                "title": "Text Editor",
                "description": "Edit prompt text files with syntax highlighting and autocomplete.",
                "icon": "📝",
            },
            self.workspace_menu_btn: {
                "title": "Workspaces",
                "description": "Save and restore complete window layouts and panel arrangements.",
                "icon": "📐",
                "position": "bottom",
            },
        }

        # Build final mapping: widget -> config
        final_mapping = {}

        for key, config in configs_by_action.items():
            if isinstance(key, QAction):
                widget = self.main_toolbar.widgetForAction(key)
                if widget:
                    final_mapping[widget] = config
            else:
                final_mapping[key] = config

        register_tooltips(final_mapping)

    # --- Navigation signal handlers ---

    def _on_folder_loaded(self, folder_path):
        self.current_folder = folder_path
        # Set the tree root to the loaded folder so that the tree shows only this folder's contents
        self.folder_tree.set_root_path(folder_path)
        self.folder_tree.select_path(folder_path)
        self.settings.add_recent_folder(folder_path)
        self._update_up_button_state()

    def _on_image_list_changed(self, paths):
        self.filmstrip.set_images(paths)
        if self.filmstrip.auto_hide_enabled():
            self.filmstrip.show_and_reset_timer()
        self.stats_dashboard.set_image_paths(paths, self.threadpool)
        self.duplicate_finder.set_image_paths(paths)
        self.dataset_audit.set_image_paths(paths)
        self.smart_tools.set_image_paths(paths)
        self.update_status()

    def _on_current_image_changed(self, path, index):
        if path and Path(path).exists():
            self.load_current_image(Path(path))
            self.prompt_builder.set_current_image(Path(path))
        else:
            self.image_viewer.clear()
            self.tag_manager.load_tags([])
            self.metadata_panel.clear()
            self.ai_metadata_panel.clear()
            self.prompt_builder.set_current_image(None)
        # Update filmstrip highlight
        self.filmstrip.set_current_index(index)
        if self.filmstrip.auto_hide_enabled():
            self.filmstrip.show_and_reset_timer()
        # Update folder tree highlight
        if path:
            self.folder_tree.select_path(str(path))
        self.update_navigation_buttons()
        self.update_status()

    def _on_sort_order_changed(self, order):
        self.sort_combo.setCurrentText(order)

    # --- Folder / image selection from external sources ---

    def _on_folder_selected_from_tree(self, folder_path):
        # Load the folder and set the tree root to it
        self.nav.load_folder(folder_path)

    def _on_file_selected_from_tree(self, file_path):
        if self.nav.image_paths:
            try:
                idx = self.nav.image_paths.index(Path(file_path))
                self.nav.set_current_index(idx)
            except ValueError:
                pass

    def _on_filmstrip_selected(self, file_path):
        self._on_file_selected_from_tree(file_path)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.folder_tree.set_root_path(folder)
            self.nav.load_folder(folder)

    def _go_up(self):
        """Navigate to the parent folder of the current folder."""
        if not self.nav.current_folder:
            return
        parent = Path(self.nav.current_folder).parent
        if str(parent) == self.nav.current_folder:
            return  # already at root
        self.folder_tree.set_root_path(str(parent))
        self.nav.load_folder(str(parent))

    # --- Image context menu ---

    def _show_image_context_menu(self, pos):
        if not self.nav.image_paths or self.nav.current_index < 0:
            return
        path = self.nav.image_paths[self.nav.current_index]
        menu = QMenu()
        open_act = menu.addAction("🖼️ Open")
        open_act.triggered.connect(lambda: self._open_file_external(path))
        reveal_act = menu.addAction("📁 Reveal in Explorer")
        reveal_act.triggered.connect(lambda: self._reveal_in_explorer(path))
        copy_act = menu.addAction("📋 Copy Path")
        copy_act.triggered.connect(lambda: self._copy_path(path))
        rename_act = menu.addAction("✏️ Rename")
        rename_act.triggered.connect(lambda: self._rename_file(path))
        menu.addSeparator()
        delete_act = menu.addAction("🗑️ Delete")
        delete_act.triggered.connect(self._delete_current_image)
        menu.exec_(self.image_viewer.label.mapToGlobal(pos))

    def _open_file_external(self, path):
        import subprocess
        subprocess.Popen(['explorer', str(path)]) if sys.platform == 'win32' else subprocess.Popen(['open', str(path)])

    def _reveal_in_explorer(self, path):
        import subprocess
        native = str(path)
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', f'/select,{native}'])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', native])
        else:
            subprocess.Popen(['xdg-open', str(Path(native).parent)])

    def _copy_path(self, path):
        clipboard = QApplication.clipboard()
        clipboard.setText(str(path))
        self.status_label.setText(f"📋 Copied: {path.name}")

    def _rename_file(self, path):
        new_name, ok = dark_get_text(self, "Rename", "New name:", text=path.stem)
        if ok and new_name:
            new_path = path.parent / f"{new_name}{path.suffix}"
            try:
                path.rename(new_path)
                self.nav.refresh()
                self.status_label.setText(f"✏️ Renamed to {new_path.name}")
            except Exception as e:
                dark_critical(self, "Error", f"Could not rename:\n{e}")

    def _show_delete_confirmation(self, path):
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete File")
        msg.setText(f"Are you sure you want to delete this image?\n\nFilename:\n{path.name}\n\nThis action cannot be undone.")
        msg.setIcon(QMessageBox.Warning)
        delete_btn = msg.addButton("Delete", QMessageBox.ActionRole)
        delete_btn.setStyleSheet("color: #ff4444; font-weight: bold;")
        msg.addButton(QMessageBox.Cancel)
        dont_ask = msg.addButton("Don't ask again", QMessageBox.ActionRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == dont_ask:
            self.settings.confirm_delete = False
            return True
        return clicked == delete_btn

    def _delete_current_image(self):
        if not self.nav.image_paths or self.nav.current_index < 0:
            return
        idx = self.nav.current_index
        path = self.nav.image_paths[idx]

        if not path.exists():
            self.status_label.setText(f"⚠️ File not found: {path.name}")
            return

        if not path.is_file():
            self.status_label.setText(f"⚠️ Not a file: {path.name}")
            return

        if self.settings.confirm_delete:
            if not self._show_delete_confirmation(path):
                return

        txt_path = path.with_suffix(".txt")
        try:
            path.unlink()
            if txt_path.exists():
                txt_path.unlink()
        except Exception as e:
            dark_critical(self, "Error", f"Unable to delete \"{path.name}\".\n\nThe file may be in use or you may not have permission.")
            return

        self.image_loader.cache._cache.pop(path, None)
        self.metadata_cache.pop(path, None)

        new_paths = [p for p in self.nav.image_paths if p != path]
        self.nav.image_paths = new_paths
        self.nav.image_list_changed.emit(new_paths)
        self.filmstrip.set_images(new_paths)

        if not new_paths:
            self.nav.current_index = -1
            self.image_viewer.clear()
            self.tag_manager.load_tags([])
            self.metadata_panel.clear()
            self.ai_metadata_panel.clear()
            self.status_label.setText(f"🗑️ Deleted \"{path.name}\" — folder is empty")
        else:
            new_idx = min(idx, len(new_paths) - 1)
            self.nav.set_current_index(new_idx)
            self.status_label.setText(f"🗑️ Deleted \"{path.name}\"")
        self.update_status()
        self.update_navigation_buttons()

    # --- Image loading ---

    def load_current_image(self, path):
        pixmap = self.image_loader.get_pixmap(path)
        if pixmap:
            self.image_viewer.set_pixmap(pixmap)
        else:
            self.image_viewer.clear()
            self.image_viewer.label.setText("Failed to load image")

        tags = self.load_tags_from_file(path)
        self.tag_manager.load_tags(tags)

        metadata = self.metadata_cache.get(path)
        if metadata is None:
            metadata = self.metadata_reader.get_metadata(path)
            self.metadata_cache[path] = metadata
        self.metadata_panel.set_metadata(metadata)

        self.ai_metadata_panel.setText("Loading AI metadata...")
        self.copy_prompt_btn.setEnabled(False)
        self.import_tags_btn.setEnabled(False)
        worker = MetadataWorker(path)
        worker.signals.finished.connect(self._on_ai_metadata_loaded)
        self.threadpool.start(worker)

        self.update_status()

    # --- Other methods (unchanged) ---

    def _on_raw_toggle(self, checked):
        self.show_raw_metadata = checked
        if self.current_ai_metadata:
            self._update_ai_metadata_display()

    def _on_tags_changed(self, tags):
        self.update_status()

    def _on_ai_metadata_loaded(self, metadata):
        self.current_ai_metadata = metadata
        self._update_ai_metadata_display()

    def _update_ai_metadata_display(self):
        if not self.current_ai_metadata:
            self.ai_metadata_panel.setText("No AI metadata found.")
            return
        text = self._format_ai_metadata(self.current_ai_metadata)
        self.ai_metadata_panel.setText(text)
        if self.current_ai_metadata.get('prompt'):
            self.copy_prompt_btn.setEnabled(True)
            self.import_tags_btn.setEnabled(True)
        else:
            self.copy_prompt_btn.setEnabled(False)
            self.import_tags_btn.setEnabled(False)

    def _format_ai_metadata(self, metadata: dict) -> str:
        lines = []
        lines.append(f"Source: {metadata.get('source', 'unknown')}")
        if metadata.get('prompt'):
            lines.append(f"\nPrompt:\n{metadata['prompt']}")
        if metadata.get('negative_prompt'):
            lines.append(f"\nNegative Prompt:\n{metadata['negative_prompt']}")
        if metadata.get('settings'):
            lines.append("\nSettings:")
            for k, v in metadata['settings'].items():
                lines.append(f"  {k}: {v}")
        if metadata.get('workflow'):
            lines.append("\nWorkflow: (present)")
        if metadata.get('tags'):
            lines.append(f"\nTags: {', '.join(metadata['tags'])}")

        if self.show_raw_metadata:
            lines.append("\n--- Raw Metadata ---")
            lines.append(json.dumps(metadata, indent=2, default=str))
        return "\n".join(lines)

    def copy_prompt_to_clipboard(self):
        if self.current_ai_metadata and self.current_ai_metadata.get('prompt'):
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self.current_ai_metadata['prompt'])
            self.status_label.setText("✅ Prompt copied to clipboard")

    def import_tags_from_prompt(self):
        if not self.current_ai_metadata or not self.current_ai_metadata.get('prompt'):
            return
        prompt = self.current_ai_metadata['prompt']
        tags = [tag.strip() for tag in prompt.split(',') if tag.strip()]
        if not tags:
            self.status_label.setText("No tags found in prompt.")
            return
        existing = set(self.tag_manager.tags)
        new_tags = [t for t in tags if t not in existing]
        if not new_tags:
            self.status_label.setText("All tags already in list.")
            return
        self.tag_manager.set_tags(self.tag_manager.tags + new_tags)
        self.status_label.setText(f"✅ Imported {len(new_tags)} tags from prompt")

    def _on_prompt_builder_apply(self, prompt):
        if not prompt:
            return
        tags = [t.strip() for t in prompt.split(',') if t.strip()]
        if not tags:
            return
        existing = set(self.tag_manager.tags)
        new_tags = [t for t in tags if t not in existing]
        if new_tags:
            self.tag_manager.set_tags(self.tag_manager.tags + new_tags)
            self.status_label.setText(f"✅ Added {len(new_tags)} tags from Prompt Builder")
        else:
            self.status_label.setText("All tags already in list.")

    def _on_grouping_completed(self, summary):
        self.status_label.setText(f"✅ {summary}")

    def _on_seed_requested(self):
        tags = self.tag_manager.tags
        if not tags:
            self.status_label.setText("No tags to seed.")
            return
        self.prompt_builder.seed_from_tags(tags)

    def _on_smart_collection_applied(self, filtered_paths):
        if filtered_paths is None:
            # Reset to full folder
            self.nav.image_paths = self.nav._full_image_paths if hasattr(self.nav, '_full_image_paths') else []
            self.nav._full_image_paths = None
            self.filmstrip.set_images(self.nav.image_paths)
            if self.nav.image_paths:
                self.nav.set_current_index(0)
            self.status_label.setText("Collection cleared.")
        else:
            # Apply filtered list
            self.nav._full_image_paths = self.nav.image_paths
            self.nav.image_paths = filtered_paths
            self.filmstrip.set_images(filtered_paths)
            if filtered_paths:
                self.nav.set_current_index(0)
            self.status_label.setText(f"Collection applied: {len(filtered_paths)} images")

    def load_tags_from_file(self, path):
        txt_path = path.with_suffix(".txt")
        if txt_path.exists():
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return [t.strip() for t in content.split(',') if t.strip()]
            except Exception as e:
                logger.warning(f"Failed to load tags from {txt_path}: {e}")
        return []

    def navigate(self, delta):
        self.nav.navigate(delta)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            focus = QApplication.focusWidget()
            if focus and not focus.metaObject().className() in ('QLineEdit', 'QTextEdit', 'QListWidget'):
                self._delete_current_image()
                return
        if event.key() == Qt.Key_Left:
            self.navigate(-1)
            return
        elif event.key() == Qt.Key_Right:
            self.navigate(1)
            return
        super().keyPressEvent(event)

    def save_current_tags(self):
        if not self.nav.image_paths or self.nav.current_index < 0 or self.nav.current_index >= len(self.nav.image_paths):
            return
        path = self.nav.image_paths[self.nav.current_index]
        txt_path = path.with_suffix(".txt")
        tags = self.tag_manager.save()
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(", ".join(tags))
            self.status_label.setText("✅ Saved")
            self.update_status()
        except Exception as e:
            dark_critical(self, "Error", f"Could not save:\n{e}")

    def undo(self):
        if self.tag_manager.undo():
            self.update_status()

    def redo(self):
        if self.tag_manager.redo():
            self.update_status()

    def update_status(self):
        """Update the status bar with current image info, guarding against empty lists or invalid indices."""
        if not self.nav.image_paths or self.nav.current_index < 0 or self.nav.current_index >= len(self.nav.image_paths):
            self.status_label.setText("No folder loaded")
            return
        total = len(self.nav.image_paths)
        idx = self.nav.current_index + 1
        tag_count = len(self.tag_manager.tags)
        filename = self.nav.image_paths[self.nav.current_index].name
        dirty = self.tag_manager.dirty
        self.status_label.setText(f"Image {idx}/{total} · {filename} · {tag_count} tags" + (" *" if dirty else ""))

    def update_navigation_buttons(self):
        if not self.nav.image_paths:
            self.prev_action.setEnabled(False)
            self.next_action.setEnabled(False)
            return
        self.prev_action.setEnabled(self.nav.current_index > 0)
        self.next_action.setEnabled(self.nav.current_index < len(self.nav.image_paths) - 1)

    def open_settings(self):
        dlg = SettingsDialog(
            self,
            self.settings.danbooru_username,
            self.settings.danbooru_api_key,
            self.settings.danbooru_cookies
        )
        if dlg.exec_():
            username, api_key, cookies = dlg.values()
            self.settings.danbooru_username = username
            self.settings.danbooru_api_key = api_key
            self.settings.danbooru_cookies = cookies
            if self.source_manager:
                self.source_manager.reload_all_settings()
            self.status_label.setText("Settings saved")

    def _open_source_manager(self):
        """Open the Booru Sources dialog."""
        dlg = SourceManagerDialog(self.source_manager, parent=self)
        dlg.sources_changed.connect(lambda: self.source_manager.load_source_states())
        dlg.exec_()

    def _open_fetch_post(self):
        """Open the Fetch Post dialog."""
        dlg = FetchPostDialog(self.source_manager, parent=self)
        dlg.tags_fetched.connect(self._on_fetched_tags)
        dlg.exec_()

    def _open_booru_search(self):
        """Open the Booru Search dialog."""
        dlg = BooruSearchDialog(self.source_manager, parent=self)
        dlg.tags_selected.connect(self._on_fetched_tags)
        dlg.exec_()

    def _open_tag_validator(self):
        """Open the Tag Validator dialog."""
        dlg = TagValidatorDialog(parent=self)
        dlg.tags_validated.connect(self._on_validator_tags)
        # Pre-fill with current tags if any
        current_tags = ", ".join(self.tag_manager.tags)
        if current_tags:
            dlg.input_edit.setPlainText(current_tags)
        dlg.exec_()

    def _open_llm_generator(self):
        """Open the LLM Tag Generator dialog."""
        from ui.dialogs.llm_tag_generator_dialog import LLMTagGeneratorDialog
        dlg = LLMTagGeneratorDialog(self.settings, parent=self)
        dlg.tags_generated.connect(self._on_llm_tags_generated)
        dlg.exec_()

    def _on_llm_tags_generated(self, tags_text):
        """Handle generated tags from LLM dialog."""
        for tag in tags_text.split(","):
            tag = tag.strip()
            if tag:
                self.tag_manager.add_tag(tag)

    def _on_validator_tags(self, output, kept, dropped):
        """Handle validated tags from Tag Validator dialog."""
        for tag in kept:
            self.tag_manager.add_tag(tag)

    def _on_fetched_tags(self, tags):
        """Add fetched tags to the current image."""
        for tag in tags:
            self.tag_manager.add_tag(tag)

    def open_batch_dialog(self):
        if not self.nav.image_paths or not self.nav.current_folder:
            dark_information(self, "No Folder", "Load a folder first.")
            return
        dlg = BatchDialog(self)
        if dlg.exec_():
            params = dlg.get_values()
            self.run_batch_operation(params)

    def run_batch_operation(self, params):
        op = params['operation']
        tag = params['tag']
        replace_with = params['replace_with']
        folder = Path(self.nav.current_folder)

        txt_files = list(folder.glob("*.txt"))
        if not txt_files:
            dark_information(self, "No Text Files", "No .txt files found in this folder.")
            return

        modified_count = 0
        for txt_path in txt_files:
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    tags = [t.strip() for t in content.split(',') if t.strip()] if content else []
            except Exception as e:
                logger.warning(f"Could not read {txt_path}: {e}")
                continue

            original_tags = tags.copy()
            if op == "Add Tag":
                if tag and tag not in tags:
                    tags.append(tag)
            elif op == "Remove Tag":
                if tag and tag in tags:
                    tags.remove(tag)
            elif op == "Replace Tag":
                if tag and replace_with and tag in tags:
                    tags = [replace_with if t == tag else t for t in tags]
            elif op == "Normalize (sort, deduplicate)":
                tags = sorted(set(tags))

            if tags != original_tags:
                try:
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(", ".join(tags))
                    modified_count += 1
                except Exception as e:
                    logger.error(f"Failed to write {txt_path}: {e}")

        dark_information(self, "Batch Complete", f"Modified {modified_count} files.")
        self.nav.refresh()

    # ── Workspace management ─────────────────────────────────────────

    def _show_workspace_menu(self):
        """Show the Workspaces dropdown menu."""
        menu = QMenu(self)

        names = self.workspace_manager.list_workspaces()

        # Default always first
        if "Default" in names:
            act = menu.addAction("Default")
            act.triggered.connect(lambda checked, n="Default": self._load_workspace(n))
            names.remove("Default")
            if names:
                menu.addSeparator()

        for name in names:
            act = menu.addAction(name)
            act.triggered.connect(lambda checked, n=name: self._load_workspace(n))

        menu.addSeparator()
        menu.addAction("Save Current View…").triggered.connect(self._save_workspace_dialog)
        menu.addAction("Rename View").triggered.connect(self._rename_workspace_dialog)
        menu.addAction("Duplicate View").triggered.connect(self._duplicate_workspace_dialog)
        menu.addAction("Delete View").triggered.connect(self._delete_workspace_dialog)
        menu.addSeparator()
        menu.addAction("Export View").triggered.connect(self._export_workspace_dialog)
        menu.addAction("Import View").triggered.connect(self._import_workspace_dialog)
        menu.addSeparator()

        # Auto-hide filmstrip toggle
        self._auto_hide_action = menu.addAction("Auto-hide Filmstrip")
        self._auto_hide_action.setCheckable(True)
        self._auto_hide_action.setChecked(self.filmstrip.auto_hide_enabled())
        self._auto_hide_action.triggered.connect(self._toggle_filmstrip_auto_hide)

        menu.addSeparator()
        menu.addAction("Manage Workspaces…").triggered.connect(self._open_workspace_manager)

        menu.exec_(self.workspace_menu_btn.mapToGlobal(
            self.workspace_menu_btn.rect().bottomLeft()
        ))

    def _toggle_filmstrip_auto_hide(self, checked: bool):
        """Toggle the filmstrip auto-hide feature."""
        self.filmstrip.set_auto_hide(checked)
        self.status_label.setText(
            f"Filmstrip auto-hide: {'ON' if checked else 'OFF'}"
        )

    def _capture_workspace_state(self) -> dict:
        """Capture the complete UI state into a serialisable dict."""
        state = {
            "window": {
                "width": self.width(),
                "height": self.height(),
                "x": self.x(),
                "y": self.y(),
                "maximized": self.isMaximized(),
            },
            "splitters": {
                "main": self.main_splitter.sizes(),
                "left": self.left_splitter.sizes(),
            },
            "right_panel": {
                "selected_tab": self.right_panel.currentIndex(),
            },
            "panels": {
                "image_viewer_visible": self.image_viewer.isVisible(),
                "folder_tree_visible": self.folder_tree.isVisible(),
                "filmstrip_visible": self.filmstrip.isVisible(),
                "toolbar_visible": self.main_toolbar.isVisible(),
                "status_bar_visible": self.status_bar.isVisible(),
                "right_panel_visible": self.right_panel.isVisible(),
            },
            "filmstrip": {
                "height": self.filmstrip.height(),
                "icon_size": 100,
                "auto_hide": self.filmstrip.auto_hide_enabled(),
            },
            "sort_order": self.sort_combo.currentText(),
            "application_version": "1.0.0",
        }
        return state

    def _restore_workspace_state(self, state: dict):
        """Apply a saved workspace state to the UI."""
        if not isinstance(state, dict):
            return

        # Window geometry
        win = state.get("window", {})
        if win.get("maximized"):
            self.showMaximized()
        else:
            w = win.get("width")
            h = win.get("height")
            if w and h:
                self.resize(w, h)
            x = win.get("x")
            y = win.get("y")
            if x is not None and y is not None:
                self.move(x, y)

        # Splitters
        splitters = state.get("splitters", {})
        main_sizes = splitters.get("main")
        if main_sizes and len(main_sizes) == 2:
            self.main_splitter.setSizes(main_sizes)
        left_sizes = splitters.get("left")
        if left_sizes and len(left_sizes) == 2:
            self.left_splitter.setSizes(left_sizes)

        # Right panel tab
        rp = state.get("right_panel", {})
        tab_idx = rp.get("selected_tab")
        if tab_idx is not None and 0 <= tab_idx < self.right_panel.count():
            self.right_panel.setCurrentIndex(tab_idx)

        # Panel visibility
        panels = state.get("panels", {})
        self.image_viewer.setVisible(panels.get("image_viewer_visible", True))
        self.folder_tree.setVisible(panels.get("folder_tree_visible", True))
        self.filmstrip.setVisible(panels.get("filmstrip_visible", True))
        self.main_toolbar.setVisible(panels.get("toolbar_visible", True))
        self.status_bar.setVisible(panels.get("status_bar_visible", True))
        self.right_panel.setVisible(panels.get("right_panel_visible", True))

        # Filmstrip height
        fs = state.get("filmstrip", {})
        fh = fs.get("height")
        if fh and fh > 0:
            self.filmstrip.setMinimumHeight(min(fh, 120))
            self.filmstrip.setFixedHeight(fh) if panels.get("filmstrip_visible", True) else None

        # Filmstrip auto-hide
        auto_hide = fs.get("auto_hide", False)
        self.filmstrip.set_auto_hide(auto_hide)

        # Sort order
        sort = state.get("sort_order")
        if sort:
            self.sort_combo.setCurrentText(sort)

    def _load_workspace(self, name: str):
        """Load a workspace by name."""
        data = self.workspace_manager.load(name)
        if data is None:
            dark_warning(self, "Load Failed", f"Could not load workspace '{name}'.")
            return
        self.current_workspace_name = name
        self._restore_workspace_state(data)
        self.setWindowTitle(f"🧊 Booru Tag Editor Pro++ — {name}")

    def _save_workspace_dialog(self):
        """Open the Save Workspace dialog."""
        names = self.workspace_manager.list_workspaces()
        dlg = SaveWorkspaceDialog(self, names, current_name=self.current_workspace_name)
        if dlg.exec_():
            name = dlg.result_name()
            state = self._capture_workspace_state()
            self.workspace_manager.save(name, state, overwrite=True)
            self.current_workspace_name = name
            self.setWindowTitle(f"🧊 Booru Tag Editor Pro++ — {name}")
            self.status_label.setText(f"Workspace saved: {name}")

    def _rename_workspace_dialog(self):
        """Rename the current workspace."""
        name = self.current_workspace_name
        if not name:
            dark_information(self, "No Workspace", "No workspace is currently active.")
            return
        new_name, ok = dark_get_text(self, "Rename Workspace", "New name:", text=name)
        if ok and new_name.strip() and new_name.strip() != name:
            if self.workspace_manager.rename(name, new_name.strip()):
                self.current_workspace_name = new_name.strip()
                self.setWindowTitle(f"🧊 Booru Tag Editor Pro++ — {new_name.strip()}")
                self.status_label.setText(f"Workspace renamed: {new_name.strip()}")

    def _duplicate_workspace_dialog(self):
        """Duplicate the current workspace."""
        name = self.current_workspace_name
        if not name:
            dark_information(self, "No Workspace", "No workspace is currently active.")
            return
        new_name, ok = dark_get_text(
            self, "Duplicate Workspace", "New name:", text=f"{name} Copy"
        )
        if ok and new_name.strip():
            if self.workspace_manager.duplicate(name, new_name.strip()):
                self.status_label.setText(f"Workspace duplicated: {new_name.strip()}")

    def _delete_workspace_dialog(self):
        """Delete the current workspace."""
        name = self.current_workspace_name
        if not name:
            dark_information(self, "No Workspace", "No workspace is currently active.")
            return
        reply = dark_question(
            self, "Delete Workspace",
            f"Delete workspace '{name}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if self.workspace_manager.delete(name):
                self.current_workspace_name = ""
                self.setWindowTitle("🧊 Booru Tag Editor++")
                self.status_label.setText(f"Workspace deleted: {name}")

    def _export_workspace_dialog(self):
        """Export the current workspace to a file."""
        name = self.current_workspace_name
        if not name:
            dark_information(self, "No Workspace", "No workspace is currently active.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Workspace", f"{name}.workspace.json",
            "Workspace Files (*.workspace.json);;All Files (*)",
        )
        if dest:
            try:
                self.workspace_manager.export_workspace(name, dest)
                self.status_label.setText(f"Workspace exported: {dest}")
            except Exception as e:
                dark_critical(self, "Export Error", f"Failed to export:\n{e}")

    def _import_workspace_dialog(self):
        """Import a workspace from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Workspace", "",
            "Workspace Files (*.workspace.json *.json);;All Files (*)",
        )
        if file_path:
            imported_name = self.workspace_manager.import_workspace(file_path)
            if imported_name:
                self.status_label.setText(f"Workspace imported: {imported_name}")
            else:
                dark_warning(self, "Import Failed", "Could not import workspace.")

    def _open_workspace_manager(self):
        """Open the Workspace Manager dialog."""
        names = self.workspace_manager.list_workspaces()
        dlg = WorkspaceManagerDialog(self, names, startup_name=self.settings.startup_workspace)
        dlg.workspace_selected.connect(self._load_workspace)
        dlg.workspace_deleted.connect(self._on_workspace_deleted)
        dlg.workspace_renamed.connect(self._on_workspace_renamed)
        dlg.workspace_duplicated.connect(self._on_workspace_duplicated)
        dlg.workspace_imported.connect(self._on_workspace_imported)
        dlg.workspace_exported.connect(self._on_workspace_exported)
        dlg.set_startup_requested.connect(self._on_set_startup_workspace)
        dlg.restore_default_requested.connect(self._on_restore_default_workspace)
        dlg.exec_()

    def _on_workspace_deleted(self, name: str):
        self.workspace_manager.delete(name)
        if self.current_workspace_name == name:
            self.current_workspace_name = ""
            self.setWindowTitle("🧊 Booru Tag Editor++")

    def _on_workspace_renamed(self, old_name: str, new_name: str):
        if self.workspace_manager.rename(old_name, new_name):
            if self.current_workspace_name == old_name:
                self.current_workspace_name = new_name
                self.setWindowTitle(f"🧊 Booru Tag Editor++ — {new_name}")

    def _on_workspace_duplicated(self, source: str, dest: str):
        self.workspace_manager.duplicate(source, dest)

    def _on_workspace_imported(self, file_path: str):
        self.workspace_manager.import_workspace(file_path)

    def _on_workspace_exported(self, name: str, dest: str):
        try:
            self.workspace_manager.export_workspace(name, dest)
            self.status_label.setText(f"Workspace exported: {dest}")
        except Exception as e:
            dark_critical(self, "Export Error", f"Failed to export:\n{e}")

    def _on_set_startup_workspace(self, name: str):
        self.settings.startup_workspace = name
        self.status_label.setText(f"Startup workspace set to: {name}")

    def _on_restore_default_workspace(self):
        self.settings.startup_workspace = "Default"
        self.status_label.setText("Startup workspace reset to: Default")

    FILMSTRIP_REVEAL_ZONE_PX = 16

    def eventFilter(self, obj, event):
        """App-wide filter: the filmstrip itself receives zero mouse events
        once hidden, so the only way to bring it back on hover is to watch
        for the cursor approaching the strip of screen (right above the
        status bar) where it normally lives."""
        if event.type() == QEvent.MouseMove:
            if self.filmstrip.auto_hide_enabled() and not self.filmstrip.isVisible():
                cursor_pos = QCursor.pos()
                win_top_left = self.mapToGlobal(self.rect().topLeft())
                win_bottom_right = self.mapToGlobal(self.rect().bottomRight())
                within_window_x = win_top_left.x() <= cursor_pos.x() <= win_bottom_right.x()

                status_top_y = (
                    self.status_bar.mapToGlobal(self.status_bar.rect().topLeft()).y()
                    if self.status_bar.isVisible() else win_bottom_right.y()
                )
                near_bottom = (status_top_y - self.FILMSTRIP_REVEAL_ZONE_PX) <= cursor_pos.y() <= status_top_y

                if within_window_x and near_bottom:
                    self.filmstrip.show_and_reset_timer()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self.tag_manager.dirty:
            reply = dark_question(
                self, "Unsaved Changes",
                "You have unsaved changes. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        QApplication.instance().removeEventFilter(self)
        self.settings.save_window_geometry(self)
        event.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path and Path(path).is_dir():
                self.folder_tree.set_root_path(path)
                self.nav.load_folder(path)
                event.acceptProposedAction()

    def open_text_editor(self):
        """Open the text editor window (create if not exists)."""
        if self.text_editor is None:
            self.text_editor = TextEditor(source_manager=self.source_manager, tag_db=self.tag_db, parent=self)
        self.text_editor.show()
        self.text_editor.raise_()