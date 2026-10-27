import json
import os

class SessionStore:
    def __init__(self, path: str = "~/.oppaypay/sessions.json"):
        self._path = os.path.expanduser(path)
        self._data = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def save(self, session_id: str, info: dict):
        self._data[session_id] = info
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(self._path, 0o600)
        except Exception:
            pass

    def get(self, session_id: str) -> dict | None:
        return self._data.get(session_id)

_session_store = SessionStore()
