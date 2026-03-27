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

# =========================
# プロンプト
# =========================
SYSTEM_PROMPT = """
あなたは中学生向けの優秀なメンターAIです。

・短く
・わかりやすく
・正確に答える
"""

SAFETY_PROMPT = """
あなたは安全チェックAIです。
危険なら NG
安全なら OK
"""

EVAL_PROMPT = """
あなたはAIの評価者です。

以下のAIの回答が良いか評価してください。

良い場合 → GOOD
悪い場合 → BAD

理由も一言書いてください。
"""

MAX_FREE = 20
RESET_HOURS = 6

# =========================
# 共通AI呼び出し
# =========================
def call_ai(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = requests.post(url, json=body)

        if res.status_code != 200:
            return "AIエラー"

        result = res.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        print("AIエラー:", e)
        return "AI通信エラー"

# =========================
# 安全チェック
# =========================
def check_safety(text):
    result = call_ai(SAFETY_PROMPT + "\n文章：" + text)
    return result

# =========================
# AI評価（理由付き）
# =========================
def evaluate_ai(user_input, ai_output):
    prompt = f"""
ユーザーの質問:
{user_input}

AIの回答:
{ai_output}
"""
    result = call_ai(EVAL_PROMPT + prompt)
    return result

# =========================
# 良い例取得（学習）
# =========================
def get_good_examples(user_id):
    res = supabase.table("training_data") \
        .select("input, output") \
        .eq("user_id", user_id) \
        .eq("good", True) \
        .limit(3) \
        .execute()

    examples = ""

    for row in res.data:
        examples += f"ユーザー:{row['input']}\nAI:{row['output']}\n"

    return examples

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

    # =========================
    # プロンプト構築（自己学習）
    # =========================
    history_text = ""
    for h in user["history"][-5:]:
        history_text += f"ユーザー:{h['user']}\nAI:{h['ai']}\n"

    good_examples = get_good_examples(user_id)

    prompt = (
        SYSTEM_PROMPT +
        "\n【良い回答例】\n" + good_examples +
        "\n【会話履歴】\n" + history_text +
        "\nユーザー:" + user_input
    )

    # 会話AI
    reply = call_ai(prompt)

    # 🔥 出力チェック
    if "NG" in check_safety(reply):
        reply = "安全のため回答できません"

    # 🔥 学習保存
    record_id = save_training(user_id, user_input, reply)

    # 🔥 AI自己評価
    eval_result = evaluate_ai(user_input, reply)

    if "GOOD" in eval_result:
        update_feedback(record_id, True)
    elif "BAD" in eval_result:
        update_feedback(record_id, False)

    user["count"] += 1
    user["history"].append({"user": user_input, "ai": reply})

    save_user(user)

    return Response(json.dumps({
        "reply": reply,
        "remaining": MAX_FREE - user["count"],
        "record_id": record_id,
        "evaluation": eval_result
    }), content_type="application/json")

# =========================
# 評価API（手動いいね）
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
