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
        return [p for p in raw if p]

    @recent_folders.setter
    def recent_folders(self, folders):
        folders = [str(p) for p in folders if p]
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

    @property
    def startup_workspace(self):
        return self.get("startup_workspace", "Default")

    @startup_workspace.setter
    def startup_workspace(self, value):
        self.set("startup_workspace", value)

    # --- Gelbooru ---
    @property
    def gelbooru_user_id(self):
        return self.get("gelbooru_user_id", "")

    @gelbooru_user_id.setter
    def gelbooru_user_id(self, value):
        self.set("gelbooru_user_id", value)

    @property
    def gelbooru_api_key(self):
        return self.get("gelbooru_api_key", "")

    @gelbooru_api_key.setter
    def gelbooru_api_key(self, value):
        self.set("gelbooru_api_key", value)

    @property
    def gelbooru_cookies(self):
        return self.get("gelbooru_cookies", "")

    @gelbooru_cookies.setter
    def gelbooru_cookies(self, value):
        self.set("gelbooru_cookies", value)

    # --- Rule34 ---
    @property
    def rule34_user_id(self):
        return self.get("rule34_user_id", "")

    @rule34_user_id.setter
    def rule34_user_id(self, value):
        self.set("rule34_user_id", value)

    @property
    def rule34_api_key(self):
        return self.get("rule34_api_key", "")

    @rule34_api_key.setter
    def rule34_api_key(self, value):
        self.set("rule34_api_key", value)

    # --- yande.re ---
    @property
    def yandere_api_key(self):
        return self.get("yandere_api_key", "")

    @yandere_api_key.setter
    def yandere_api_key(self, value):
        self.set("yandere_api_key", value)

    @property
    def yandere_cookies(self):
        return self.get("yandere_cookies", "")

    @yandere_cookies.setter
    def yandere_cookies(self, value):
        self.set("yandere_cookies", value)

    # --- Konachan ---
    @property
    def konachan_api_key(self):
        return self.get("konachan_api_key", "")

    @konachan_api_key.setter
    def konachan_api_key(self, value):
        self.set("konachan_api_key", value)

    @property
    def konachan_cookies(self):
        return self.get("konachan_cookies", "")

    @konachan_cookies.setter
    def konachan_cookies(self, value):
        self.set("konachan_cookies", value)

    # --- LLM ---
    @property
    def llm_server_url(self):
        return self.get("llm_server_url", "http://localhost:11434")

    @llm_server_url.setter
    def llm_server_url(self, value):
        self.set("llm_server_url", value)

    @property
    def llm_model(self):
        return self.get("llm_model", "qwen3:1.7b")

    @llm_model.setter
    def llm_model(self, value):
        self.set("llm_model", value)

    @property
    def llm_temperature(self):
        val = self.get("llm_temperature", "0.4")
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.4

    @llm_temperature.setter
    def llm_temperature(self, value):
        self.set("llm_temperature", str(value))

    @property
    def llm_max_tokens(self):
        val = self.get("llm_max_tokens", "500")
        try:
            return int(val)
        except (TypeError, ValueError):
            return 500

    @llm_max_tokens.setter
    def llm_max_tokens(self, value):
        self.set("llm_max_tokens", str(value))

    @property
    def llm_enable_thinking(self):
        val = self.get("llm_enable_thinking", "false")
        return str(val).lower() in ("true", "1", "yes")

    @llm_enable_thinking.setter
    def llm_enable_thinking(self, value):
        self.set("llm_enable_thinking", "true" if value else "false")

    @property
    def llm_api_key(self):
        return self.get("llm_api_key", "")

    @llm_api_key.setter
    def llm_api_key(self, value):
        self.set("llm_api_key", value)

    @property
    def llm_timeout(self):
        val = self.get("llm_timeout", "120")
        try:
            return int(val)
        except (TypeError, ValueError):
            return 120

    @llm_timeout.setter
    def llm_timeout(self, value):
        self.set("llm_timeout", str(value))