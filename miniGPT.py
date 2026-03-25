# python
from flask import Flask, request, Response
import json
import requests
import os
import traceback

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
# APIキー（Render）
# =========================
API_KEY = os.getenv("CatAI")  # ←環境変数名に合わせて設定する

# =========================
# 記憶ファイル
# =========================
MEMORY_FILE = "memory.json"

# =========================
# 記憶ロード
# =========================
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"user_name": "", "history": []}

# =========================
# 記憶保存
# =========================
def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception:
        print("保存エラー:\n", traceback.format_exc())

memory = load_memory()

# =========================
# Gemini通信
# =========================
def ask_gemini(user_input):
    # APIキー確認
    if not API_KEY:
        return "APIキーが設定されていません"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    # 履歴
    history_text = ""
    for h in memory["history"][-5:]:
        history_text += f"ユーザー: {h.get('user','')}\nAI: {h.get('ai','')}\n"

    # 名前
    name_text = f"ユーザーの名前は{memory['user_name']}です。\n" if memory["user_name"] else ""

    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = requests.post(url, json=body, timeout=10)

        # ステータスチェック
        if res.status_code != 200:
            # 可能なら本文も表示して原因を確認
            try:
                return f"AIエラー: {res.status_code} - {res.text}"
            except Exception:
                return f"AIエラー: {res.status_code}"

        result = res.json()

        return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception:
        print("通信エラー:\n", traceback.format_exc())
        return "通信エラーが発生しました"

# =========================
# API
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_input = data.get("message", "")

        # 名前登録
        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            memory["user_name"] = name
            reply = f"{name}さん、覚えました！よろしくね！"
        else:
            reply = ask_gemini(user_input)

        # 履歴保存
        memory["history"].append({
            "user": user_input,
            "ai": reply
        })

        save_memory()

        return Response(
            json.dumps({"reply": reply}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception:
        print("サーバー処理エラー:\n", traceback.format_exc())
        return Response(
            json.dumps({"reply": "サーバーエラーが発生しました"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

# =========================
# 起動（Render 用に PORT を利用）
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
