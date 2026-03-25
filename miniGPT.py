# python
# ファイル: `miniGPT.py`
from flask import Flask, request, Response, jsonify
import json
import requests
import os
import traceback
from pathlib import Path

app = Flask(__name__)

# =========================
# メンター設定
# =========================
SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
相手を否定せず、やさしく導いてください。
"""

# =========================
# APIキー（Render / env）
# - 環境変数名: CATAI_API_KEY（互換で CatAI を参照）
# =========================
API_KEY = os.getenv("CATAI_API_KEY") or os.getenv("CatAI")
if not API_KEY:
    # 起動時にログ出力（デバッグ用）
    print("警告: 環境変数 `CATAI_API_KEY` または `CatAI` が設定されていません。")

# =========================
# 記憶ファイル
# =========================
MEMORY_FILE = Path("memory.json")

def load_memory():
    try:
        if MEMORY_FILE.exists():
            text = MEMORY_FILE.read_text(encoding="utf-8").strip()
            if not text:
                return {"user_name": "", "history": []}
            data = json.loads(text)
            # 最低限のスキーマ保証
            if not isinstance(data, dict):
                return {"user_name": "", "history": []}
            data.setdefault("user_name", "")
            data.setdefault("history", [])
            return data
    except Exception:
        print("load_memory error:", traceback.format_exc())
    return {"user_name": "", "history": []}

def save_memory(memory):
    try:
        # atomic に上書き
        tmp = MEMORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(MEMORY_FILE)
        print("Saved memory to", MEMORY_FILE)
    except Exception:
        print("保存エラー:\n", traceback.format_exc())

memory = load_memory()

# =========================
# requests セッション（再利用）
# =========================
session = requests.Session()
session.headers.update({"Content-Type": "application/json; charset=utf-8"})

# =========================
# Gemini 通信
# =========================
def ask_gemini(user_input):
    if not API_KEY:
        return "APIキーが設定されていません"

    # NOTE: Google Generative API のエンドポイントやリクエスト形式は将来的に変わる可能性があるため、
    # 実際に使用しているAPIドキュメントに合わせて body を調整してください。
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    # 履歴（直近5件）
    history_text = ""
    for h in memory.get("history", [])[-5:]:
        history_text += f"ユーザー: {h.get('user','')}\nAI: {h.get('ai','')}\n"

    name_text = f"ユーザーの名前は{memory.get('user_name','')}です。\n" if memory.get("user_name") else ""
    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = session.post(url, json=body, timeout=15)

        if res.status_code != 200:
            # レスポンス本文も返してデバッグしやすくする
            try:
                return f"AIエラー: {res.status_code} - {res.text}"
            except Exception:
                return f"AIエラー: {res.status_code}"

        result = res.json()
        # 安全にパース
        try:
            candidates = result.get("candidates")
            if isinstance(candidates, list) and candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts")
                if isinstance(parts, list) and parts:
                    text = parts[0].get("text")
                    if isinstance(text, str):
                        return text
        except Exception:
            print("レスポンス解析エラー:", traceback.format_exc())

        # フォールバック
        return "AIの応答を解析できませんでした"

    except requests.RequestException:
        print("通信エラー:\n", traceback.format_exc())
        return "通信エラーが発生しました"

# =========================
# API エンドポイント
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_input = data.get("message", "")

        if not isinstance(user_input, str) or user_input.strip() == "":
            return jsonify({"reply": "メッセージが空です"}), 400

        # 名前登録処理（簡易）
        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            memory["user_name"] = name
            reply = f"{name}さん、覚えました！よろしくね！"
        else:
            reply = ask_gemini(user_input)

        memory.setdefault("history", []).append({"user": user_input, "ai": reply})
        save_memory(memory)

        return Response(
            json.dumps({"reply": reply}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception:
        print("サーバー処理エラー:\n", traceback.format_exc())
        return Response(
            json.dumps({"reply": "サーバーエラーが発生しました"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=500
        )

# ヘルスチェック
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "memory_present": MEMORY_FILE.exists()})

# 起動（Render 用に PORT を利用）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 本番は gunicorn などを推奨
    app.run(host="0.0.0.0", port=port)
