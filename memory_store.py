# python
from pathlib import Path
import json
import threading
import base64
import time
import os
from typing import Dict, Any, List

class MemoryStore:
    """
    JSONベースの簡易メモリストア。
    ファイルは ./memories に保存され、ファイル毎にスレッドロックを持つ。
    """

    def __init__(self, base_dir: str = "memories", max_history: int = 500):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _safe_name(self, account_id: str) -> str:
        if not account_id:
            account_id = "default"
        b = base64.urlsafe_b64encode(account_id.encode("utf-8")).decode("ascii")
        b = b.rstrip("=")
        return f"memory_{b}.json"

    def _path(self, account_id: str) -> Path:
        return self.base_dir / self._safe_name(account_id)

    def _get_lock(self, path: Path) -> threading.Lock:
        key = str(path)
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def load(self, account_id: str) -> Dict[str, Any]:
        """
        指定アカウントのメモリを読み込む。存在しない場合はデフォルト構造を返す。
        """
        p = self._path(account_id)
        lock = self._get_lock(p)
        with lock:
            if not p.exists():
                return {"user_name": "", "history": [], "mentor_prompt": ""}
            try:
                text = p.read_text(encoding="utf-8").strip()
                if not text:
                    return {"user_name": "", "history": [], "mentor_prompt": ""}
                data = json.loads(text)
                if not isinstance(data, dict):
                    return {"user_name": "", "history": [], "mentor_prompt": ""}
                data.setdefault("user_name", "")
                data.setdefault("history", [])
                data.setdefault("mentor_prompt", "")
                return data
            except Exception:
                return {"user_name": "", "history": [], "mentor_prompt": ""}

    def save(self, account_id: str, memory: Dict[str, Any]) -> None:
        """
        指定アカウントのメモリをアトミックに保存する。
        """
        p = self._path(account_id)
        lock = self._get_lock(p)
        with lock:
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(tmp), str(p))

    def append_history(self, account_id: str, user_text: str, ai_text: str) -> None:
        """
        履歴を追加し、必要ならトリミングする。
        """
        mem = self.load(account_id)
        mem.setdefault("history", [])
        mem["history"].append({"user": user_text, "ai": ai_text, "ts": int(time.time())})
        if len(mem["history"]) > self.max_history:
            mem["history"] = mem["history"][-self.max_history:]
        self.save(account_id, mem)

    def set_user_name(self, account_id: str, name: str) -> None:
        mem = self.load(account_id)
        mem["user_name"] = name or ""
        self.save(account_id, mem)

    def list_accounts(self) -> List[str]:
        """
        保存されているアカウント一覧（安全なファイル名）を返す。
        """
        files = []
        for p in self.base_dir.glob("memory_*.json"):
            files.append(p.name)
        return files

    def delete(self, account_id: str) -> bool:
        """
        指定アカウントのメモリを削除する。成功すれば True。
        """
        p = self._path(account_id)
        lock = self._get_lock(p)
        with lock:
            try:
                if p.exists():
                    p.unlink()
                    return True
            except Exception:
                pass
        return False
