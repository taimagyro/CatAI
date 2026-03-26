from flask import Flask, request, Response
import json
import requests
import os

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
# ファイル設定
# =========================
MEMORY_FILE = "memory.json"
DATA_FILE = "training_data.json"  # ←追加（学習用）

# =========================
# 記憶ロード
# =========================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# =========================
# 記憶保存
# =========================
def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()

# =========================
# 学習データ保存（超重要）
# =========================
def save_training(user_input, reply):

    data = []

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.append({
        "input": user_input,
        "output": reply
    })

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =========================
# ユーザー取得
# =========================
def get_user(user_id):
    if user_id not in memory:
        memory[user_id] = {
            "name": "",
            "history": []
        }
    return memory[user_id]

# =========================
# Gemini
# =========================
def ask_gemini(user_input, user):

    if not API_KEY:
        return "APIキーがありません"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    history_text = ""
    for h in user["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

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

    except:
        return "通信エラー"

# =========================
# API
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    user_input = data.get("message", "")
    user_id = data.get("user_id", "default")

    user = get_user(user_id)

    # 名前登録
    if "名前は" in user_input:
        name = user_input.replace("名前は", "").strip()
        user["name"] = name
        reply = f"{name}さん、覚えました！"
    else:
        reply = ask_gemini(user_input, user)

    # 履歴保存
    user["history"].append({
        "user": user_input,
        "ai": reply
    })

    # 🔥 ここが今回の追加（超重要）
    save_training(user_input, reply)

    save_memory()

    return Response(
        json.dumps({"reply": reply}, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
