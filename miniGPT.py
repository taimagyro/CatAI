from flask import Flask, request, Response
import json
import requests
import os
from supabase import create_client
from datetime import datetime, timedelta
from memory_store import save_training, update_feedback

app = Flask(__name__)

API_KEY = os.getenv("CatAI")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
"""

MAX_FREE = 20
RESET_HOURS = 6

# =========================
# ユーザー取得
# =========================
def get_user(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]
    else:
        new_user = {
            "id": user_id,
            "name": "",
            "history": [],
            "count": 0,
            "last_reset": datetime.utcnow().isoformat(),
            "is_premium": False
        }
        supabase.table("users").insert(new_user).execute()
        return new_user

# =========================
# ユーザー保存
# =========================
def save_user(user):
    supabase.table("users").update({
        "name": user["name"],
        "history": user["history"],
        "count": user["count"],
        "last_reset": user["last_reset"],
        "is_premium": user.get("is_premium", False)
    }).eq("id", user["id"]).execute()

# =========================
# Gemini
# =========================
def ask_gemini(user_input, user):

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    history_text = ""
    for h in user["history"][-5:]:
        history_text += f"ユーザー: {h['user']}\nAI: {h['ai']}\n"

    prompt = SYSTEM_PROMPT + "\n" + history_text + "ユーザー: " + user_input

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    res = requests.post(url, json=body)

    if res.status_code != 200:
        return f"AIエラー: {res.status_code}"

    result = res.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

# =========================
# チャット
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    user_input = data.get("message", "")
    user_id = data.get("user_id", "default")

    user = get_user(user_id)

    now = datetime.utcnow()
    last_reset = datetime.fromisoformat(user["last_reset"])

    if now - last_reset > timedelta(hours=RESET_HOURS):
        user["count"] = 0
        user["last_reset"] = now.isoformat()

    if not user.get("is_premium") and user["count"] >= MAX_FREE:
        return Response(json.dumps({
            "reply": "制限に達しました",
            "remaining": 0
        }), content_type="application/json")

    reply = ask_gemini(user_input, user)

    # 🔥 学習保存
    save_training(user_id, user_input, reply)

    user["count"] += 1
    user["history"].append({"user": user_input, "ai": reply})

    save_user(user)

    return Response(json.dumps({
        "reply": reply,
        "remaining": MAX_FREE - user["count"]
    }), content_type="application/json")

# =========================
# 評価API（いいねボタン）
# =========================
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()

    record_id = data.get("record_id")
    is_good = data.get("good")

    update_feedback(record_id, is_good)

    return {"status": "ok"}

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
