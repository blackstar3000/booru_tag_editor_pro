from pathlib import Path
from PyQt5.QtCore import QSettings, QByteArray

class SettingsManager:
    def __init__(self, app_name="BooruTagEditorPro", org_name="BossGame"):
        self.settings = QSettings(org_name, app_name)

    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)

    @property
    def danbooru_username(self):
        return self.get("danbooru_username", "")

    @danbooru_username.setter
    def danbooru_username(self, value):
        self.set("danbooru_username", value)

    @property
    def danbooru_api_key(self):
        return self.get("danbooru_api_key", "")

    @danbooru_api_key.setter
    def danbooru_api_key(self, value):
        self.set("danbooru_api_key", value)

    @property
    def danbooru_cookies(self):
        return self.get("danbooru_cookies", "")

    @danbooru_cookies.setter
    def danbooru_cookies(self, value):
        self.set("danbooru_cookies", value)

    @property
    def recent_folders(self):
        raw = self.settings.value("recent_folders", [])
        if isinstance(raw, QByteArray):
            raw = bytes(raw).decode('utf-8').strip('[]').replace('"', '').split(',') if raw else []
        elif isinstance(raw, str):
            raw = [p.strip() for p in raw.split(',') if p.strip()]
        elif isinstance(raw, list):
            raw = [str(p) for p in raw]
        else:
            raw = []
        return [p for p in raw if p and Path(p).exists()]

    @recent_folders.setter
    def recent_folders(self, folders):
        folders = [str(p) for p in folders if p and Path(p).exists()]
        self.set("recent_folders", folders)

    @property
    def confirm_delete(self):
        val = self.get("confirm_delete", "true")
        return str(val).lower() in ("true", "1", "yes")

    @confirm_delete.setter
    def confirm_delete(self, value):
        self.set("confirm_delete", "true" if value else "false")

    def add_recent_folder(self, folder_path):
        folders = self.recent_folders
        path = str(folder_path)
        if path in folders:
            folders.remove(path)
        folders.insert(0, path)
        self.recent_folders = folders[:10]

    def save_window_geometry(self, window):
        self.set("window_geometry", window.saveGeometry())
        self.set("window_state", window.saveState())

    def restore_window_geometry(self, window):
        geom = self.get("window_geometry")
        if geom:
            window.restoreGeometry(geom)
        state = self.get("window_state")
        if state:
            window.restoreState(state)