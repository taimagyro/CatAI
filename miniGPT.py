# python
# ファイル: `miniGPT_multiaccount.py`
from flask import Flask, request, Response, jsonify
import json
import requests
import os
import traceback
from pathlib import Path
import re

app = Flask(__name__)

SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
相手を否定せず、やさしく導いてください。
"""

API_KEY =os.getenv("CatAI")
if not API_KEY:
    print("警告: 環境変数 `CATAI_API_KEY` または `CatAI` が設定されていません。")

MEMORY_DIR = Path("memories")
MEMORY_DIR.mkdir(exist_ok=True)

session = requests.Session()
session.headers.update({"Content-Type": "application/json; charset=utf-8"})

def safe_id(account_id: str) -> str:
    if not account_id:
        return "default"
    return re.sub(r'[^A-Za-z0-9_\-]', '_', account_id)[:64]

def memory_path(account_id: str) -> Path:
    return MEMORY_DIR / f"memory_{safe_id(account_id)}.json"

def load_memory(account_id: str):
    p = memory_path(account_id)
    try:
        if p.exists():
            text = p.read_text(encoding="utf-8").strip()
            if text:
                data = json.loads(text)
                if isinstance(data, dict):
                    data.setdefault("user_name", "")
                    data.setdefault("history", [])
                    data.setdefault("mentor_prompt", SYSTEM_PROMPT)
                    return data
    except Exception:
        print("load_memory error:", traceback.format_exc())
    return {"user_name": "", "history": [], "mentor_prompt": SYSTEM_PROMPT}

def save_memory(account_id: str, memory: dict):
    p = memory_path(account_id)
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        print("save_memory error:", traceback.format_exc())

def ask_gemini(user_input: str, memory: dict):
    if not API_KEY:
        return "APIキーが設定されていません"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    history_text = ""
    for h in memory.get("history", [])[-5:]:
        history_text += f"ユーザー: {h.get('user','')}\nAI: {h.get('ai','')}\n"

    name_text = f"ユーザーの名前は{memory.get('user_name','')}です。\n" if memory.get("user_name") else ""
    prompt = (memory.get("mentor_prompt", SYSTEM_PROMPT) or SYSTEM_PROMPT) + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        res = session.post(url, json=body, timeout=15)
        if res.status_code != 200:
            try:
                return f"AIエラー: {res.status_code} - {res.text}"
            except Exception:
                return f"AIエラー: {res.status_code}"
        result = res.json()
        candidates = result.get("candidates")
        if isinstance(candidates, list) and candidates:
            parts = candidates[0].get("content", {}).get("parts")
            if isinstance(parts, list) and parts:
                text = parts[0].get("text")
                if isinstance(text, str):
                    return text
        return "AIの応答を解析できませんでした"
    except requests.RequestException:
        print("通信エラー:\n", traceback.format_exc())
        return "通信エラーが発生しました"

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_input = data.get("message", "")
        account_id = data.get("account_id") or request.headers.get("X-Account-ID") or "default"
        account_id = str(account_id)

        if not isinstance(user_input, str) or user_input.strip() == "":
            return jsonify({"reply": "メッセージが空です"}), 400

        memory = load_memory(account_id)

        # 名前登録（簡易）
        if user_input.startswith("名前は"):
            name = user_input.replace("名前は", "").strip()
            memory["user_name"] = name
            reply = f"{name}さん、覚えました！よろしくね！"
        else:
            reply = ask_gemini(user_input, memory)

        memory.setdefault("history", []).append({"user": user_input, "ai": reply})
        save_memory(account_id, memory)

        return Response(json.dumps({"reply": reply}, ensure_ascii=False), content_type="application/json; charset=utf-8")
    except Exception:
        print("サーバー処理エラー:\n", traceback.format_exc())
        return Response(json.dumps({"reply": "サーバーエラーが発生しました"}, ensure_ascii=False), content_type="application/json; charset=utf-8", status=500)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    try:
        if request.method == "GET":
            account_id = request.args.get("account_id") or request.headers.get("X-Account-ID") or "default"
            memory = load_memory(account_id)
            return jsonify({
                "account_id": account_id,
                "user_name": memory.get("user_name", ""),
                "mentor_prompt": memory.get("mentor_prompt", SYSTEM_PROMPT)
            })
        else:
            data = request.get_json(silent=True) or {}
            account_id = data.get("account_id") or request.headers.get("X-Account-ID") or "default"
            memory = load_memory(account_id)
            if "user_name" in data:
                memory["user_name"] = data.get("user_name") or ""
            if "mentor_prompt" in data:
                memory["mentor_prompt"] = data.get("mentor_prompt") or SYSTEM_PROMPT
            save_memory(account_id, memory)
            return jsonify({"status": "ok", "account_id": account_id})
    except Exception:
        print("profile error:\n", traceback.format_exc())
        return jsonify({"status": "error"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
