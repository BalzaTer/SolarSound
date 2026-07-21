import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


def collect_file_characteristics(file_path: str) -> Dict[str, Any]:
    """Collecte des informations utiles sur le fichier problématique."""
    if not file_path:
        return {}

    size_bytes = 0
    exists = os.path.exists(file_path)
    if exists:
        try:
            size_bytes = os.path.getsize(file_path)
        except OSError:
            size_bytes = 0

    name = os.path.basename(file_path)
    extension = os.path.splitext(file_path)[1].lower()
    return {
        "exists": exists,
        "name": name,
        "extension": extension,
        "size_bytes": size_bytes,
        "modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat() if exists else None,
    }


def append_error_log(message: str, file_path: Optional[str], log_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
    """Ajoute une entrée JSON dans un fichier de log pour les erreurs de lecture."""
    if log_path is None:
        log_path = os.path.join(os.getcwd(), "playback_errors.log")

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "file_path": file_path or "",
    }
    payload.update(collect_file_characteristics(file_path or ""))
    if context:
        payload.update(context)

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return log_path
