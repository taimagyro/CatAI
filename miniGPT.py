from flask import Flask, request, Response
import json
import requests
import os

app = Flask(__name__)

SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
"""

API_KEY = os.getenv("GEMINI_API_KEY")

MEMORY_FILE = "memory.json"

# =========================
# 記憶ロード
# =========================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"user_name": "", "history": []}

# =========================
# 記憶保存
# =========================
def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()

# =========================
# Gemini
# =========================
def ask_gemini(user_input):

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

    history_text = ""
    for h in memory["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

    name_text = f"ユーザーの名前は{memory['user_name']}です。\n" if memory["user_name"] else ""

    prompt = SYSTEM_PROMPT + "\n" + name_text + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    res = requests.post(url, json=body)
    result = res.json()

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "エラーが発生しました。"

# =========================
# API
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    user_input = data.get("message", "")

    if "名前は" in user_input:
        name = user_input.replace("名前は", "").strip()
        memory["user_name"] = name
        reply = f"{name}さん、覚えました！"
    else:
        reply = ask_gemini(user_input)

    memory["history"].append({"user": user_input, "ai": reply})

    save_memory()

    return Response(
        json.dumps({"reply": reply}, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
