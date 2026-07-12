GLASS_STYLE = """
/* ── Base ──────────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI", "Helvetica Neue", "Inter", sans-serif;
}
QMainWindow, QWidget {
    background: #0d0f14;
    color: #e0e0e0;
}
QMainWindow::separator {
    background: rgba(139, 92, 246, 0.15);
    width: 3px;
    margin: 0;
}
QMainWindow::separator:hover {
    background: rgba(139, 92, 246, 0.4);
}

/* ── Menu Bar ──────────────────────────────────────────────────── */
QMenuBar {
    background: rgba(13, 15, 20, 0.8);
    color: #ccc;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    padding: 2px 4px;
}
QMenuBar::item {
    padding: 6px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background: rgba(139, 92, 246, 0.2);
}
QMenu {
    background: rgba(18, 20, 28, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 6px;
    color: #ccc;
}
QMenu::item:selected {
    background: rgba(139, 92, 246, 0.25);
    color: #fff;
}
QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 4px 10px;
}

/* ── Toolbar ───────────────────────────────────────────────────── */
QToolBar {
    background: rgba(13, 15, 20, 0.6);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    padding: 4px 8px;
    spacing: 4px;
}
QToolBar::separator {
    width: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 6px 6px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 12px;
    color: #bbb;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background: rgba(139, 92, 246, 0.12);
    border-color: rgba(139, 92, 246, 0.2);
    color: #fff;
}
QToolBar QToolButton:pressed {
    background: rgba(139, 92, 246, 0.25);
}

/* ── Tab Widget (Right Panel) ──────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    background: rgba(16, 18, 26, 0.7);
    top: -1px;
}
QTabBar {
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: #888;
    border: none;
    padding: 10px 16px;
    margin: 2px 2px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
}
QTabBar::tab:hover {
    color: #ccc;
    background: rgba(255, 255, 255, 0.04);
}
QTabBar::tab:selected {
    color: #fff;
    background: rgba(139, 92, 246, 0.15);
    border-bottom: 2px solid #8B5CF6;
}

/* ── Buttons ───────────────────────────────────────────────────── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #7C3AED);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 12px;
    min-height: 18px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9B6CF6, stop:1 #8C4AED);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6B2AED, stop:1 #5B1AED);
}
QPushButton:disabled {
    background: rgba(139, 92, 246, 0.25);
    color: rgba(255, 255, 255, 0.3);
}

/* ── Input Fields ──────────────────────────────────────────────── */
QLineEdit, QTextEdit {
    background: rgba(16, 18, 26, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    color: #eee;
    font-size: 13px;
    selection-background-color: rgba(139, 92, 246, 0.4);
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid rgba(139, 92, 246, 0.5);
    background: rgba(16, 18, 26, 0.85);
}
QLineEdit::placeholder {
    color: rgba(255, 255, 255, 0.25);
}

/* ── ComboBox ──────────────────────────────────────────────────── */
QComboBox {
    background: rgba(16, 18, 26, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 12px;
    color: #ccc;
    min-width: 80px;
}
QComboBox:hover {
    border-color: rgba(139, 92, 246, 0.3);
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: rgba(18, 20, 28, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(139, 92, 246, 0.25);
    color: #ccc;
    outline: none;
}

/* ── List Widget (Filmstrip / Smart Tools) ─────────────────────── */
QListWidget {
    background: rgba(16, 18, 26, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    padding: 6px 10px;
    margin: 2px 0;
    color: #ddd;
}
QListWidget::item:selected {
    background: rgba(139, 92, 246, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #fff;
}
QListWidget::item:hover:!selected {
    background: rgba(255, 255, 255, 0.05);
}

/* ── Tree View (Folder Tree) ───────────────────────────────────── */
QTreeView {
    background: transparent;
    border: none;
    outline: none;
    color: #bbb;
    font-size: 13px;
}
QTreeView::item {
    padding: 5px 8px;
    border-radius: 6px;
    margin: 1px 4px;
}
QTreeView::item:selected {
    background: rgba(139, 92, 246, 0.2);
    color: #fff;
}
QTreeView::item:hover:!selected {
    background: rgba(255, 255, 255, 0.04);
}
QTreeView::branch {
    background: transparent;
}
QTreeView::branch:has-children:closed {
    border-image: none;
    image: none;
    border-left: none;
}
QTreeView::branch:has-children:open {
    border-image: none;
    image: none;
    border-left: none;
}
QTreeView::indicator {
    width: 14px;
    height: 14px;
    border-radius: 4px;
}

/* ── Scroll Bars ───────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(139, 92, 246, 0.35);
    border-radius: 4px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(139, 92, 246, 0.55);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(139, 92, 246, 0.35);
    border-radius: 4px;
    min-width: 40px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(139, 92, 246, 0.55);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ── Status Bar ────────────────────────────────────────────────── */
QStatusBar {
    background: rgba(13, 15, 20, 0.7);
    color: #888;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
    font-size: 12px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Splitter Handle ───────────────────────────────────────────── */
QSplitter::handle {
    background: rgba(139, 92, 246, 0.12);
    border-radius: 2px;
}
QSplitter::handle:hover {
    background: rgba(139, 92, 246, 0.35);
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}

/* ── Check Box ─────────────────────────────────────────────────── */
QCheckBox {
    spacing: 8px;
    color: #bbb;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(16, 18, 26, 0.7);
}
QCheckBox::indicator:checked {
    background: #8B5CF6;
    border-color: #8B5CF6;
}
QCheckBox::indicator:hover {
    border-color: rgba(139, 92, 246, 0.5);
}

/* ── Radio Button ──────────────────────────────────────────────── */
QRadioButton {
    spacing: 8px;
    color: #bbb;
    font-size: 12px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(16, 18, 26, 0.7);
}
QRadioButton::indicator:checked {
    background: #8B5CF6;
    border-color: #8B5CF6;
}

/* ── Group Box ─────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #ccc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #aaa;
}

/* ── ToolTip (suppressed in favor of custom tooltip system) ─────── */
QToolTip {
    background: transparent;
    color: transparent;
    border: none;
    padding: 0;
    font-size: 0;
}

/* ── Dialog ────────────────────────────────────────────────────── */
QDialog {
    background: #0d0f14;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}

/* ── Message Box ───────────────────────────────────────────────── */
QMessageBox {
    background: #0d0f14;
}
QMessageBox QLabel {
    color: #ccc;
    font-size: 13px;
}

/* ── Scroll Area ───────────────────────────────────────────────── */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}

/* ── Widget containers with glass effect ───────────────────────── */
QWidget[class="glass-panel"] {
    background: rgba(16, 18, 26, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
}
"""
