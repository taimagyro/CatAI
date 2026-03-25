from flask import Flask, request, Response
import json
import requests
import os

app = Flask(__name__)

# =========================
# メンターAI設定（超重要）
# =========================
SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
相手を否定せず、成長をサポートすることを最優先にしてください。
"""

# APIキー（Renderから取得）
API_KEY = os.getenv("GEMINI_API_KEY")

# =========================
# 自分のAI（記憶）
# =========================
memory = {
    "user_name": "",
    "history": []
}

# =========================
# Geminiに送る関数
# =========================
def ask_gemini(user_input):

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    # 会話履歴を文字にする
    history_text = ""
    for h in memory["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

    # 名前があれば追加
    name_text = ""
    if memory["user_name"]:
        name_text = f"ユーザーの名前は{memory['user_name']}です。\n"

    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    res = requests.post(url, headers=headers, json=body)
    result = res.json()

    try:
        reply = result["candidates"][0]["content"]["parts"][0]["text"]
    except:
        reply = "エラーが発生しました。"

    return reply

# =========================
# チャットAPI
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    user_input = data.get("message", "")

    # 名前登録
    if "名前は" in user_input:
        name = user_input.replace("名前は", "").strip()
        memory["user_name"] = name

        reply = f"{name}さん、覚えました！これからよろしくね！"
    else:
        reply = ask_gemini(user_input)

    # 履歴保存
    memory["history"].append({
        "user": user_input,
        "ai": reply
    })

    return Response(
        json.dumps({"reply": reply}, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
