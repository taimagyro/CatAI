from flask import Flask, request, Response
import json
import requests
import os
from supabase import create_client
from datetime import datetime, timedelta

app = Flask(__name__)

# =========================
# 設定
# =========================
SYSTEM_PROMPT = """
あなたは優しくて賢いメンターAIです。
中学生にもわかりやすく説明してください。
"""

API_KEY = os.getenv("CatAI")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            "last_reset": datetime.utcnow().isoformat()
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
        "last_reset": user["last_reset"]
    }).eq("id", user["id"]).execute()

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
    try:
        data = request.get_json()

        user_input = data.get("message", "")
        user_id = data.get("user_id", "default")

        user = get_user(user_id)

        # =========================
        # リセット処理
        # =========================
        now = datetime.utcnow()
        last_reset = user.get("last_reset")

        if last_reset:
            last_reset = datetime.fromisoformat(last_reset)

            if now - last_reset > timedelta(hours=RESET_HOURS):
                user["count"] = 0
                user["last_reset"] = now.isoformat()

        # =========================
        # 制限チェック
        # =========================
        if user.get("count", 0) >= MAX_FREE:
            return Response(
                json.dumps({
                    "reply": "無料回数（20回）を超えました。\n6時間後にまた使えます！"
                }, ensure_ascii=False),
                content_type="application/json; charset=utf-8"
            )

        # =========================
        # 名前登録
        # =========================
        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            user["name"] = name
            reply = f"{name}さん、覚えました！"
        else:
            reply = ask_gemini(user_input, user)

        # =========================
        # カウント増加
        # =========================
        user["count"] = user.get("count", 0) + 1

        # =========================
        # 履歴保存
        # =========================
        user["history"].append({
            "user": user_input,
            "ai": reply
        })

        save_user(user)

        return Response(
            json.dumps({"reply": reply}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception as e:
        print(e)
       return Response(
    json.dumps({
        "reply": reply,
        "remaining": MAX_FREE - user["count"]
    }, ensure_ascii=False),
    content_type="application/json; charset=utf-8"
)

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)            "name": "",
            "history": []
        }
        supabase.table("users").insert(new_user).execute()
        return new_user

# =========================
# ユーザー保存
# =========================
def save_user(user):

    supabase.table("users").update({
        "name": user["name"],
        "history": user["history"]
    }).eq("id", user["id"]).execute()

# =========================
# 学習データ保存
# =========================
def save_training(user_input, reply):

    supabase.table("training_data").insert({
        "input": user_input,
        "output": reply
    }).execute()

# =========================
# Gemini
# =========================
def ask_gemini(user_input, user):

    if not API_KEY:
        return "AIzaSyC0NXuR5tg1Eyq3D8-mbR6qFh4LipjlXXA"

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

    try:
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

        # 履歴更新
        user["history"].append({
            "user": user_input,
            "ai": reply
        })

        # 保存
        save_user(user)

        # 学習データ
        save_training(user_input, reply)

        return Response(
            json.dumps({"reply": reply}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    except Exception as e:
        print(e)
        return Response(
            json.dumps({"reply": "サーバーエラー"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
