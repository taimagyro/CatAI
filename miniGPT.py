from flask import Flask, request, Response
import json
import requests
import os
from supabase import create_client
from datetime import datetime, timedelta

app = Flask(__name__)

# =========================
# Supabase設定
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabaseキーが設定されていません")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 設定
# =========================
SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
必ず日本語で答えてください。
"""

MAX_FREE = 20
RESET_HOURS = 6

# =========================
# Llama（ローカルAI）
# =========================
def ask_llama(prompt):
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": SYSTEM_PROMPT + "\n" + prompt,
                "stream": False
            }
        )

        if res.status_code != 200:
            return f"AIエラー: {res.status_code}"

        return res.json()["response"]

    except Exception as e:
        print("Llamaエラー:", e)
        return "AI通信エラー"

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
    supabase.table("users").update({
        "name": user["name"],
        "history": user["history"],
        "count": user["count"],
        "last_reset": user["last_reset"],
        "is_premium": user.get("is_premium", False)
    }).eq("id", user["id"]).execute()

# =========================
# API
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        user_input = data.get("message", "")
        user_id = data.get("user_id", "default")

        user = get_user(user_id)

        # リセット処理
        now = datetime.utcnow()
        last_reset = user.get("last_reset")

        if last_reset:
            last_reset = datetime.fromisoformat(last_reset)
            if now - last_reset > timedelta(hours=RESET_HOURS):
                user["count"] = 0
                user["last_reset"] = now.isoformat()

        # 制限
        if not user.get("is_premium") and user.get("count", 0) >= MAX_FREE:
            return Response(
                json.dumps({
                    "reply": "無料回数（20回）を超えました。6時間後にまた使えます！",
                    "remaining": 0
                }, ensure_ascii=False),
                content_type="application/json; charset=utf-8"
            )

        # 名前登録
        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            user["name"] = name
            reply = f"{name}さん、覚えました！"
        else:
            # 🔥 ここがLlama
            reply = ask_llama(user_input)

        # カウント
        user["count"] = user.get("count", 0) + 1

        # 履歴
        user["history"].append({
            "user": user_input,
            "ai": reply
        })

        save_user(user)

        return Response(
            json.dumps({
                "reply": reply,
                "remaining": MAX_FREE - user["count"]
            }, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception as e:
        print("サーバーエラー:", e)
        return Response(
            json.dumps({"reply": "サーバーエラー"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
