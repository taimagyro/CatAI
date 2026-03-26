from flask import Flask, request, Response
import json
import requests
import os

# 🔥 ここが重要（分離した記憶を読み込む）
from memory_store import load_memory, save_memory, get_user, save_training

app = Flask(__name__)

# =========================
# メンターAI設定
# =========================
SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
"""

# =========================
# APIキー
# =========================
API_KEY = os.getenv("CatAI")

# =========================
# 記憶読み込み
# =========================
memory = load_memory()

# =========================
# Gemini
# =========================
def ask_gemini(user_input, user):

    if not API_KEY:
        return "AIzaSyC0NXuR5tg1Eyq3D8-mbR6qFh4LipjlXXA"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    # 会話履歴
    history_text = ""
    for h in user["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

    # 名前情報
    name_text = f"ユーザーの名前は{user['name']}です。\n" if user["name"] else ""

    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = requests.post(url, json=body)

        if res.status_code != 200:
            return f"AIエラー: {res.status_code}"

        result = res.json()

        return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return "通信エラー"

# =========================
# API
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json()

        user_input = data.get("message", "")
        user_id = data.get("user_id", "default")

        # 👤 ユーザーごとの記憶取得
        user = get_user(memory, user_id)

        # 名前登録
        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            user["name"] = name
            reply = f"{name}さん、覚えました！"
        else:
            reply = ask_gemini(user_input, user)

        # 🧠 会話履歴保存
        user["history"].append({
            "user": user_input,
            "ai": reply
        })

        # 🔥 学習データ保存（未来のAI用）
        save_training(user_input, reply)

        # 💾 メモリ保存
        save_memory(memory)

        return Response(
            json.dumps({"reply": reply}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception as e:
        return Response(
            json.dumps({"reply": "サーバーエラーが発生しました"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
