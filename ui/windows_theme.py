# ui/windows_theme.py
"""
Centralized Windows dark title bar and Mica/Acrylic backdrop helpers.

Every top-level window in the application should call set_dark_title_bar()
in its showEvent to get a consistent dark native Windows title bar.

Usage:
    from ui.windows_theme import set_dark_title_bar

    class MyDialog(QDialog):
        def showEvent(self, event):
            super().showEvent(event)
            set_dark_title_bar(self)
"""

import ctypes
import platform
from ctypes import wintypes

import logging
logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"

# Try to load DWM API once at module level
_dwmapi = None
_user32 = None
if _IS_WINDOWS:
    try:
        _dwmapi = ctypes.windll.dwmapi
        _user32 = ctypes.windll.user32
    except Exception:
        pass


def set_dark_title_bar(widget):
    """Apply dark Windows 10/11 title bar to a widget.

    Safe to call on any platform — silently does nothing on non-Windows
    or if the DWM API is unavailable.

    Args:
        widget: Any QWidget (QMainWindow, QDialog, etc.) with a valid winId().
    """
    if not _IS_WINDOWS or _dwmapi is None:
        return

    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return
        hwnd = wintypes.HWND(hwnd)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        _dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


def enable_mica_backdrop(widget):
    """Apply Windows 11 Mica/Acrylic backdrop with graceful fallback.

    Tries DWMWA_SYSTEMBACKDROP_TYPE first (Win11 22000+),
    then falls back to SetWindowCompositionAttribute acrylic (Win10 1903+).

    Args:
        widget: Any QWidget with a valid winId().

    Returns:
        True if a backdrop was applied, False otherwise.
    """
    if not _IS_WINDOWS or _dwmapi is None:
        return False

    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return False
        hwnd = wintypes.HWND(hwnd)
    except Exception:
        return False

    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_MAINWINDOW = 2
    DWMSBT_TRANSIENTWINDOW = 3

    def _set_attr(attribute, value):
        val = ctypes.c_int(value)
        return _dwmapi.DwmSetWindowAttribute(
            hwnd, attribute, ctypes.byref(val), ctypes.sizeof(val)
        ) == 0

    # Always try dark mode first
    try:
        _set_attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    except Exception:
        pass

    # Try Win11 Mica backdrops
    for backdrop_type in (DWMSBT_MAINWINDOW, DWMSBT_TRANSIENTWINDOW):
        try:
            if _set_attr(DWMWA_SYSTEMBACKDROP_TYPE, backdrop_type):
                return True
        except Exception:
            pass

    # Fallback: Win10 acrylic via SetWindowCompositionAttribute
    try:
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.GradientColor = 0x99202020
        accent.AccentFlags = 2

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)

        _user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return True

    except Exception:
        return False


def dark_get_text(parent, title, label, text="", **kwargs):
    """Wrapper around QInputDialog.getText that applies dark title bar.

    Usage (drop-in replacement):
        # Before:
        text, ok = QInputDialog.getText(self, "Rename", "New name:", text=old)
        # After:
        text, ok = dark_get_text(self, "Rename", "New name:", text=old)
    """
    from PyQt5.QtWidgets import QInputDialog

    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    if text:
        dlg.setTextValue(text)
    for key, val in kwargs.items():
        setter = f"set{key[0].upper()}{key[1:]}"
        if hasattr(dlg, setter):
            getattr(dlg, setter)(val)

    set_dark_title_bar(dlg)
    ok = dlg.exec_() == QInputDialog.Accepted
    return dlg.textValue(), ok


def _dark_msgbox(icon, parent, title, text, buttons=None, default_button=None):
    """Internal helper for dark-themed QMessageBox wrappers."""
    from PyQt5.QtWidgets import QMessageBox

    dlg = QMessageBox(parent)
    dlg.setIcon(icon)
    dlg.setWindowTitle(title)
    dlg.setText(text)
    if buttons is not None:
        dlg.setStandardButtons(buttons)
    if default_button is not None:
        dlg.setDefaultButton(default_button)
    set_dark_title_bar(dlg)
    return dlg.exec_()


def dark_question(parent, title, text, buttons=None, default_button=None):
    """Drop-in for QMessageBox.question() with dark title bar."""
    from PyQt5.QtWidgets import QMessageBox
    return _dark_msgbox(
        QMessageBox.Question, parent, title, text,
        buttons or (QMessageBox.Yes | QMessageBox.No),
        default_button,
    )


def dark_information(parent, title, text, buttons=None, default_button=None):
    """Drop-in for QMessageBox.information() with dark title bar."""
    from PyQt5.QtWidgets import QMessageBox
    return _dark_msgbox(
        QMessageBox.Information, parent, title, text,
        buttons or QMessageBox.Ok,
        default_button,
    )


def dark_warning(parent, title, text, buttons=None, default_button=None):
    """Drop-in for QMessageBox.warning() with dark title bar."""
    from PyQt5.QtWidgets import QMessageBox
    return _dark_msgbox(
        QMessageBox.Warning, parent, title, text,
        buttons or QMessageBox.Ok,
        default_button,
    )


def dark_critical(parent, title, text, buttons=None, default_button=None):
    """Drop-in for QMessageBox.critical() with dark title bar."""
    from PyQt5.QtWidgets import QMessageBox
    return _dark_msgbox(
        QMessageBox.Critical, parent, title, text,
        buttons or QMessageBox.Ok,
        default_button,
    )
