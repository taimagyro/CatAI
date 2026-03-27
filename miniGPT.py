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

SAFETY_PROMPT = """
あなたはAIの安全チェック係です。
以下の文章が安全か判定してください。

危険な場合 → NG
安全な場合 → OK
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
# 保存
# =========================
def save_user(user):
    supabase.table("users").update(user).eq("id", user["id"]).execute()

# =========================
# Gemini
# =========================
def call_ai(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    res = requests.post(url, json=body)

    if res.status_code != 200:
        return "AIエラー"

    result = res.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

# =========================
# 安全チェック
# =========================
def check_safety(text):
    result = call_ai(SAFETY_PROMPT + "\n文章：" + text)
    return result

# =========================
# チャット
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    user_input = data.get("message", "")
    user_id = data.get("user_id", "default")

    user = get_user(user_id)

    # 🔥 入力チェック
    if "NG" in check_safety(user_input):
        return Response(json.dumps({
            "reply": "その内容は送信できません",
            "remaining": MAX_FREE - user["count"]
        }), content_type="application/json")

    # リセット
    now = datetime.utcnow()
    last_reset = datetime.fromisoformat(user["last_reset"])

    if now - last_reset > timedelta(hours=RESET_HOURS):
        user["count"] = 0
        user["last_reset"] = now.isoformat()

    # 制限
    if not user.get("is_premium") and user["count"] >= MAX_FREE:
        return Response(json.dumps({
            "reply": "制限に達しました",
            "remaining": 0
        }), content_type="application/json")

    # 会話AI
    history_text = ""
    for h in user["history"][-5:]:
        history_text += f"ユーザー:{h['user']}\nAI:{h['ai']}\n"

    prompt = SYSTEM_PROMPT + "\n" + history_text + "ユーザー:" + user_input

    reply = call_ai(prompt)

    # 🔥 出力チェック
    if "NG" in check_safety(reply):
        reply = "安全のため回答できません"

    # 🔥 学習保存（ID取得）
    record_id = save_training(user_id, user_input, reply)

    user["count"] += 1
    user["history"].append({"user": user_input, "ai": reply})

    save_user(user)

    return Response(json.dumps({
        "reply": reply,
        "remaining": MAX_FREE - user["count"],
        "record_id": record_id  # ←これ超重要
    }), content_type="application/json")


# =========================
# 評価API
# =========================
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()

    record_id = data.get("record_id")
    good = data.get("good")

    update_feedback(record_id, good)

    return {"status": "ok"}


# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
