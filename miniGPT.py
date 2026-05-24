from flask import Flask, request, Response
import json
import os
from supabase import create_client
from datetime import datetime, timedelta
from miniGPT import ask                          # ← これを追加
from memory_store import save_training, update_feedback  # ← これも追加

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MAX_FREE = 20
RESET_HOURS = 6

def get_user(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    if res.data:
        return res.data[0]
    new_user = {
        "id": user_id, "name": "", "history": [],
        "count": 0, "last_reset": datetime.utcnow().isoformat(), "is_premium": False
    }
    supabase.table("users").insert(new_user).execute()
    return new_user

def save_user(user):
    supabase.table("users").update({
        "name": user["name"], "history": user["history"],
        "count": user["count"], "last_reset": user["last_reset"],
        "is_premium": user.get("is_premium", False)
    }).eq("id", user["id"]).execute()

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_input = data.get("message", "")
        user_id = data.get("user_id", "default")
        user = get_user(user_id)

        now = datetime.utcnow()
        last_reset = user.get("last_reset")
        if last_reset:
            last_reset = datetime.fromisoformat(last_reset)
            if now - last_reset > timedelta(hours=RESET_HOURS):
                user["count"] = 0
                user["last_reset"] = now.isoformat()

        if not user.get("is_premium") and user.get("count", 0) >= MAX_FREE:
            return Response(
                json.dumps({"reply": "無料回数（20回）を超えました。6時間後にまた使えます！", "remaining": 0}, ensure_ascii=False),
                content_type="application/json; charset=utf-8"
            )

        if "名前は" in user_input:
            name = user_input.replace("名前は", "").strip()
            user["name"] = name
            reply = f"{name}さん、覚えました！"
        else:
            reply = ask(user_input, user["history"])  # ← miniGPTを呼ぶ

        # 学習データとして保存
        record_id = save_training(user_id, user_input, reply)

        user["count"] = user.get("count", 0) + 1
        user["history"].append({"user": user_input, "ai": reply})
        save_user(user)

        return Response(
            json.dumps({"reply": reply, "remaining": MAX_FREE - user["count"], "record_id": record_id}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print("サーバーエラー:", e)
        return Response(json.dumps({"reply": "サーバーエラー"}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# フィードバック受付
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()
    update_feedback(data.get("record_id"), data.get("good"), data.get("reason"))
    return Response(json.dumps({"status": "ok"}), content_type="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
