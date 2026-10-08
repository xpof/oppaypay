import json
import os
from pathlib import Path


class SessionStore:
    """uuidV7 -> セッション情報(access_token 等)の永続化管理"""

    def __init__(self, path: str | Path = "~/.oppaypay/session.json"):
        self._path = Path(path).expanduser()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self, session_id: str, info: dict):
        self._data[session_id] = info
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def get(self, session_id: str) -> dict | None:
        return self._data.get(session_id)

    def delete(self, session_id: str):
        self._data.pop(session_id, None)
        self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")


store = SessionStore()
