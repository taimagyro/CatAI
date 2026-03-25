# python
# ファイル: `memory_store.py`
import sqlite3
import json
import time
from typing import List, Dict, Any, Optional

class MemoryStore:
    """
    SQLiteベースのアカウントごとのメモリ管理。
    - accounts: account_id, user_name, mentor_prompt, created_at
    - messages: id, account_id, role ('user'|'ai'), content, ts
    """
    def __init__(self, db_path: str = "memories.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        self._init_schema()

    def _apply_pragmas(self):
        cur = self._conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.close()

    def _init_schema(self):
        cur = self._conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            user_name TEXT DEFAULT '',
            mentor_prompt TEXT DEFAULT '',
            created_at INTEGER
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ts INTEGER NOT NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_account_ts ON messages(account_id, ts DESC);")
        self._conn.commit()
        cur.close()

    def get_profile(self, account_id: str) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute("SELECT account_id, user_name, mentor_prompt, created_at FROM accounts WHERE account_id = ?;", (account_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return dict(row)
        # create default profile if not exists
        now = int(time.time())
        cur = self._conn.cursor()
        cur.execute("INSERT OR IGNORE INTO accounts(account_id, user_name, mentor_prompt, created_at) VALUES (?, ?, ?, ?);",
                    (account_id, "", "", now))
        self._conn.commit()
        cur.close()
        return {"account_id": account_id, "user_name": "", "mentor_prompt": "", "created_at": now}

    def set_profile(self, account_id: str, user_name: Optional[str] = None, mentor_prompt: Optional[str] = None):
        # upsert pattern
        cur = self._conn.cursor()
        cur.execute("INSERT OR IGNORE INTO accounts(account_id, user_name, mentor_prompt, created_at) VALUES (?, ?, ?, ?);",
                    (account_id, user_name or "", mentor_prompt or "", int(time.time())))
        if user_name is not None:
            cur.execute("UPDATE accounts SET user_name = ? WHERE account_id = ?;", (user_name, account_id))
        if mentor_prompt is not None:
            cur.execute("UPDATE accounts SET mentor_prompt = ? WHERE account_id = ?;", (mentor_prompt, account_id))
        self._conn.commit()
        cur.close()

    def append_message_pair(self, account_id: str, user_text: str, ai_text: str):
        ts = int(time.time())
        cur = self._conn.cursor()
        cur.executemany(
            "INSERT INTO messages(account_id, role, content, ts) VALUES (?, ?, ?, ?);",
            [(account_id, "user", user_text, ts), (account_id, "ai", ai_text, ts + 1)]
        )
        self._conn.commit()
        cur.close()

    def append_message(self, account_id: str, role: str, content: str):
        ts = int(time.time())
        cur = self._conn.cursor()
        cur.execute("INSERT INTO messages(account_id, role, content, ts) VALUES (?, ?, ?, ?);",
                    (account_id, role, content, ts))
        self._conn.commit()
        cur.close()

    def get_recent_history(self, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT role, content, ts FROM messages WHERE account_id = ? ORDER BY ts DESC LIMIT ?;",
            (account_id, limit)
        )
        rows = cur.fetchall()
        cur.close()
        # 返す順序: 古い->新しい
        return [dict(r) for r in reversed(rows)]

    def prune_history(self, account_id: str, keep: int = 200):
        # keep 最新 keep 件、古いものを削除
        cur = self._conn.cursor()
        cur.execute("""
        DELETE FROM messages WHERE id IN (
            SELECT id FROM messages WHERE account_id = ? ORDER BY ts DESC LIMIT -1 OFFSET ?
        );
        """, (account_id, keep))
        self._conn.commit()
        cur.close()

    def delete_account(self, account_id: str):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM messages WHERE account_id = ?;", (account_id,))
        cur.execute("DELETE FROM accounts WHERE account_id = ?;", (account_id,))
        self._conn.commit()
        cur.close()

    def export_account(self, account_id: str) -> Dict[str, Any]:
        profile = self.get_profile(account_id)
        history = self.get_recent_history(account_id, limit=10000)
        return {"profile": profile, "history": history}

    def close(self):
        self._conn.close()


# 簡単な使用例（Flask から呼ぶ想定）
if __name__ == "__main__":
    store = MemoryStore("memories.db")
    store.set_profile("alice", user_name="Alice", mentor_prompt="優しく導くメンターです。")
    store.append_message_pair("alice", "こんにちは", "こんにちは、調子はどう？")
    print(store.get_recent_history("alice", limit=10))
    print(json.dumps(store.export_account("alice"), ensure_ascii=False, indent=2))
    store.close()
