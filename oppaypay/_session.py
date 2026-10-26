import os
import json
from pathlib import Path

SESSION_DIR = Path.home() / ".oppaypay" / "sessions"

def save(session_id: str, data: dict):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SESSION_DIR / f"{session_id}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def get(session_id: str) -> dict | None:
    file_path = SESSION_DIR / f"{session_id}.json"
    if not file_path.exists():
        return None
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def delete(session_id: str):
    file_path = SESSION_DIR / f"{session_id}.json"
    if file_path.exists():
        file_path.unlink()