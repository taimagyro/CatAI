from flask import Flask, request, Response
import json
import requests
import os

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
API_KEY = os.getenv("CatAI")  # ←あなたの設定に合わせてる

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
    except:
        pass
    return {"user_name": "", "history": []}

# =========================
# 記憶保存
# =========================
def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except:
        print("保存エラー")

memory = load_memory()

# =========================
# Gemini通信
# =========================
def ask_gemini(user_input):

    # APIキー確認
    if not API_KEY:
        return "APIキーが設定されていません"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

    # 履歴
    history_text = ""
    for h in memory["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

    # 名前
    name_text = f"ユーザーの名前は{memory['user_name']}です。\n" if memory["user_name"] else ""

    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = requests.post(url, json=body)

        # ステータスチェック
        if res.status_code != 200:
            return f"AIエラー: {res.status_code}"

        result = res.json()

        return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
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
