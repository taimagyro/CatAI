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
あなたは中学生向けの最高のメンターAIです。

・短く
・わかりやすく
・具体的に
・やさしく
"""

SAFETY_PROMPT = "危険ならNG 安全ならOK"

EVAL_PROMPT = """
あなたはAIの評価者です。

GOOD または BAD を必ず書く
その後に理由を書く
"""

RULE_PROMPT = """
以下の良い回答の理由から
共通ルールを3つ作ってください

短くまとめること
"""

MAX_FREE = 20
RESET_HOURS = 6

# =========================
# AI呼び出し
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
    return call_ai(SAFETY_PROMPT + "\n" + text)

# =========================
# 評価
# =========================
def evaluate_ai(user_input, ai_output):

    prompt = f"""
ユーザー:{user_input}
AI:{ai_output}
"""

    result = call_ai(EVAL_PROMPT + prompt)

    if "GOOD" in result:
        return True, result
    elif "BAD" in result:
        return False, result
    else:
        return None, result

# =========================
# ルール生成🔥
# =========================
def generate_rules(user_id):

    res = supabase.table("training_data") \
        .select("reason") \
        .eq("user_id", user_id) \
        .eq("good", True) \
        .limit(5) \
        .execute()

    reasons = ""

    for row in res.data:
        reasons += row["reason"] + "\n"

    if reasons == "":
        return ""

    rules = call_ai(RULE_PROMPT + "\n" + reasons)

    return rules

# =========================
# 良い例
# =========================
def get_good_examples(user_id):

    res = supabase.table("training_data") \
        .select("input, output, reason") \
        .eq("user_id", user_id) \
        .eq("good", True) \
        .limit(3) \
        .execute()

    text = ""

    for row in res.data:
        text += f"""
ユーザー:{row['input']}
AI:{row['output']}
理由:{row['reason']}
"""

    return text

# =========================
# ユーザー
# =========================
def get_user(user_id):

    res = supabase.table("users").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]

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

def save_user(user):
    supabase.table("users").update(user).eq("id", user["id"]).execute()

# =========================
# CHAT
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    user_input = data.get("message", "")
    user_id = data.get("user_id", "default")

    user = get_user(user_id)

    # 安全チェック
    if "NG" in check_safety(user_input):
        return Response(json.dumps({"reply": "送信できません"}), content_type="application/json")

    # リセット
    now = datetime.utcnow()
    last = datetime.fromisoformat(user["last_reset"])

    if now - last > timedelta(hours=RESET_HOURS):
        user["count"] = 0
        user["last_reset"] = now.isoformat()

    # 制限
    if user["count"] >= MAX_FREE:
        return Response(json.dumps({"reply": "制限です"}), content_type="application/json")

    # =========================
    # 学習データ
    # =========================
    history = ""
    for h in user["history"][-5:]:
        history += f"ユーザー:{h['user']}\nAI:{h['ai']}\n"

    good_examples = get_good_examples(user_id)
    rules = generate_rules(user_id)

    prompt = (
        SYSTEM_PROMPT +
        "\n【ルール】\n" + rules +
        "\n【良い例】\n" + good_examples +
        "\n【履歴】\n" + history +
        "\nユーザー:" + user_input
    )

    # AI回答
    reply = call_ai(prompt)

    # 出力安全
    if "NG" in check_safety(reply):
        reply = "回答できません"

    # 保存
    record_id = save_training(user_id, user_input, reply)

    # 自己評価
    good, reason = evaluate_ai(user_input, reply)

    if good is not None:
        update_feedback(record_id, good, reason)

    # 更新
    user["count"] += 1
    user["history"].append({"user": user_input, "ai": reply})

    save_user(user)

    return Response(json.dumps({
        "reply": reply,
        "record_id": record_id,
        "evaluation": reason
    }, ensure_ascii=False), content_type="application/json")

# =========================
# フィードバック
# =========================
@app.route("/feedback", methods=["POST"])
def feedback():

    data = request.get_json()

    record_id = data.get("record_id")
    good = data.get("good")

    update_feedback(record_id, good, "user feedback")

    return {"status": "ok"}

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
def ask_llama(prompt):
    import requests

    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": "必ず日本語で答えて\n" + prompt,
            "stream": False
        }
    )

    return res.json()["response"]
